"""chantier_liquidity_capacity_2026-08-23.py

Objectif (demande utilisateur) : remplacer le calcul de compounding NON
contraint de la strategie B (EV +2,28R, risque 1,50%/trade, ~16-20 trades/
mois -> +83%/mois compose -> x1400/an, absurde) par un modele de
compounding PLAFONNE par la capacite reelle du marche (ADV mesuree, pas
supposee -- cf. recherche sourcee separee, chiffres integres ci-dessous
avec niveau de confiance explicite par instrument).

Mecanisme de plafonnement : a CHAQUE trade, le risque applique est le plus
restrictif entre (a) 1,50% du solde courant (capital personnel reel, pas de
plafond Blueberry artificiel) et (b) une fraction (1%/3%/5% teste) de l'ADV
sourcee de l'instrument concerne, convertie en risque $ via le stop reel
du trade (stop_pct = |prix_entree-stop_loss_init|/prix_entree, donnee
HISTORIQUE REELLE de la population B_tradable_pgp -- PAS les specs
market_data du moteur flotte, qui sont volontairement "unconstrained"
(price=1.0, tick_value=1.0) pour l'or/argent/palladium/platine/indices,
cf. build_market_data_with_indices -- inutilisables ici).

Approximation economique assumee (a documenter explicitement dans le
rendu) : notional_expose = risque_$ / stop_pct (P&L ~ lineaire en
notional x variation de prix, valable pour un CFD/FX/metal spot standard,
ignore les mecaniques exactes de marge/tick par broker). Le plafond de
liquidite compare ce notional a liquidity_cap_pct x ADV_USD[marche], PAS
un empilement de lots -- coherent avec la litterature de capacite
d'execution (position value vs ADV), evite de devoir re-simuler des specs
de contrat CFD non documentees.

Compounding : balance mise a jour a CHAQUE trade (continu), pas juste a
la fin du mois -- c'est ce qui produit la composition mensuelle
(~16-20 trades/mois) que le calcul non contraint decrivait. Rapporte par
snapshot de fin de mois pour lisibilite.

Reutilise EXACTEMENT la population/prior officiels de la strategie B
(point_d_bloc1_bloc2_2026-08-22.load_scenario_pgp -> B_tradable_pgp
corrigee, n=1248, Beta(625,625)) et le meme mecanisme de bootstrap par
blocs de 2 mois que le reste du projet (build_blocks / build_full_block_
bootstrap_sequence), pour une distribution EV/winrate réaliste (pas une EV
plate) -- SEULE difference avec le moteur flotte officiel : pas de
mecanique multi-firm/DD/challenge (hors sujet ici, capital personnel reel
post-strategie, pas un compte prop a faire passer une evaluation).
"""
import importlib.util
import random
import sys
import time

import numpy as np
import pandas as pd

_spec = importlib.util.spec_from_file_location("pdb", "point_d_bloc1_bloc2_2026-08-22.py")
pdb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pdb)
s18 = pdb.s18

DAY_SECONDS = 86400
MONTH_SECONDS = 365.25 / 12 * DAY_SECONDS
BLOCK_SECONDS = 2 * 30 * DAY_SECONDS
START_CAPITAL = 200_000.0
TARGET_RISK_PCT = 1.50

POP_PATH = "chantier_gold_silver_pop_B_tradable_pgp_2026-08-20.csv"

# ============================================================
# ADV sourcees (recherche web dediee, 2026-08-23) -- voir
# liquidite_capacite_marche_2026-08-23.md pour sources/confiance detaillees.
# Valeurs en USD notional/jour. "market" regroupe les variantes multi-devises
# du meme sous-jacent (ex: GOLD - AUD/EUR/GBP/USD -> meme marche spot or).
# ============================================================
ADV_USD = {
    # -- FX majors, reconstruit via parts de marche BIS 2022 (source secondaire
    # citant BIS, CompareForexBrokers/Yahoo Finance) x turnover OTC TOTAL global
    # $7 500Md/j (spot+forwards+swaps+options, PAS spot seul -- gonfle l'ADV,
    # sens conservateur pour ce modele : si meme le total ne contraint pas,
    # le spot seul (plus petit) contraindrait encore moins) -- confiance MOYENNE,
    # parts non relues sur table BIS primaire (2 tentatives de fetch direct du
    # PDF/table BIS ont echoue, PDF illisible + portail JS non statique)
    "EUR/USD": 1_700_000_000_000.0,   # 22,7% x 7 500Md$
    "USD/JPY": 1_010_000_000_000.0,   # 13,5% x 7 500Md$ -- 1ere recherche avait trouve 439Md$ (etiquete "BIS global" mais incoherent avec ce calcul, perimetre ambigu spot vs total -- figure de 1 010Md$ retenue car chaine de calcul plus tracable)
    "GBP/USD": 713_000_000_000.0,     # 9,5% x 7 500Md$ -- 1ere recherche avait trouve 432Md$ = Londres seule (BoE), remplace par la figure globale
    "USD/CAD": 413_000_000_000.0,     # 5,5% x 7 500Md$
    "AUD/USD": 383_000_000_000.0,     # 5,1% x 7 500Md$
    "USD/CHF": 293_000_000_000.0,     # 3,9% x 7 500Md$
    "NZD/USD": 40_000_000_000.0,      # NON SOURCE (2 tentatives infructueuses) -- proxy prudent (NZD=14e devise la plus tradee), confiance TRES BASSE/NON SOURCEE, a corriger si donnee trouvee
    # -- crosses JPY/EUR/GBP/CHF : NON SOURCEES (2 tentatives BIS infructueuses,
    # aucune table primaire ni source secondaire fiable trouvee) -- ordres de
    # grandeur qualitatifs seulement ("1-2 ordres de grandeur sous les majors
    # composantes", non verifie), confiance TRES BASSE/NON SOURCEE explicite
    "EUR/JPY": 60_000_000_000.0,
    "GBP/JPY": 55_000_000_000.0,
    "AUD/JPY": 25_000_000_000.0,
    "CHF/JPY": 15_000_000_000.0,
    "EUR/CHF": 20_000_000_000.0,
    "EUR/GBP": 30_000_000_000.0,
    "GBP/CHF": 15_000_000_000.0,
    # -- metaux precieux, LBMA Q4 2024 report (clearing x10 = estimation turnover), confiance MOYENNE --
    "GOLD": 430_000_000_000.0,
    "SILVER": 73_000_000_000.0,
    # -- PLATINE : 1 point de donnee trouve (volume NYMEX 61 000 contrats "jour
    # normal" + 115 000 contrats record, juin 2025, 50oz/contrat) -> 61 000*50*
    # ~1000$/oz = ~3,05Md$/j -- PAS une vraie ADV (2 points, pas une moyenne),
    # mais coherent avec l'ordre de grandeur retenu -- confiance BASSE
    "PLATINUM": 3_500_000_000.0,
    # -- PALLADIUM : AUCUNE donnee trouvee (2 sessions de recherche) -- proxy
    # qualitatif seul (marche historiquement du meme ordre de grandeur que le
    # platine), confiance TRES BASSE/NON SOURCEE explicite
    "PALLADIUM": 3_500_000_000.0,
    # -- indices --
    "DAX40": 26_500_000_000.0,          # Eurex, EUR24,58Md/j 2024 -> ~USD26,5Md, confiance HAUTE (source exchange directe)
    "NASDAQ100_EMINI": 239_000_000_000.0,  # $239Md$/j (page Schwab citant donnees CME) -- confiance MOYENNE
    "SP500_EMINI": 500_000_000_000.0,   # estimation combinee ordre de grandeur (1,5-2M contrats/j x 50$ x ~6000pts) -- pas de figure ADV directe trouvee pour le contrat E-mini seul (seulement CME firme entiere ou Micro E-mini), confiance BASSE
}

TICKER_TO_MARKET = {
    "GOLD - AUD": "GOLD", "GOLD - EUR": "GOLD", "GOLD - GBP": "GOLD", "GOLD - USD": "GOLD",
    "SILVER - AUD": "SILVER", "SILVER - EUR": "SILVER", "SILVER - USD": "SILVER",
    "PALLADIUM": "PALLADIUM", "PLATINUM": "PLATINUM",
    "DAX40 FULL0926": "DAX40", "DAX40 PERF INDEX": "DAX40",
    "NASDAQ100 - MINI NASDAQ100 FULL0926": "NASDAQ100_EMINI", "NASDAQ100 INDEX": "NASDAQ100_EMINI",
    "S&P500 - MINI S&P500 FULL0926": "SP500_EMINI",
}


def market_for(ticker):
    return TICKER_TO_MARKET.get(ticker, ticker)


def load_population_with_stop_pct():
    pop = pd.read_csv(POP_PATH)
    pop["date_creation"] = pd.to_datetime(pop["date_creation"])
    pop["resolution_time_est"] = pd.to_datetime(pop["resolution_time_est"])
    sub = pop.sort_values("date_creation").reset_index(drop=True)
    stop_pct = (sub["prix_entree"] - sub["stop_loss_init"]).abs() / sub["prix_entree"]
    return pop, sub, stop_pct.to_numpy()


def build_trades_with_stop_pct(pop, sub_sorted, stop_pct_arr, wr_draw, rng):
    trades, slot_arrivals = s18.build_flexible_population_with_rr(pop, wr_draw, 1.0, False, rng)
    assert len(trades) == len(stop_pct_arr), "desynchronisation tri population / stop_pct"
    for t, sp in zip(trades, stop_pct_arr):
        t["stop_pct"] = float(sp)
    return trades, slot_arrivals


def simulate_one(trades, slot_arrivals, target_duration_days, liquidity_cap_pct, rng_boot, alpha_post, beta_post,
                  start_capital=None):
    """liquidity_cap_pct=None -> pas de plafond (regime non contraint, reference).
    start_capital=None -> utilise START_CAPITAL (200k$, cas standard)."""
    start_capital = START_CAPITAL if start_capital is None else start_capital
    from real_cash_risk_year1_block_bootstrap import build_blocks
    from reference_metrics_final import build_full_block_bootstrap_sequence

    blocks = build_blocks(trades, slot_arrivals, BLOCK_SECONDS)
    target_duration = target_duration_days * DAY_SECONDS
    raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, BLOCK_SECONDS, rng_boot, target_duration)
    keep = [i for i, s in enumerate(raw_slots) if s < target_duration]
    raw_trades = [raw_trades[i] for i in keep]
    raw_slots = [raw_slots[i] for i in keep]
    order = sorted(range(len(raw_trades)), key=lambda i: raw_slots[i])

    balance = start_capital
    n_trades = 0
    n_capped = 0
    month_snapshots = {}
    max_month = int(target_duration_days * DAY_SECONDS // MONTH_SECONDS) + 1

    for i in order:
        trade = raw_trades[i]
        now = raw_slots[i]
        stop_pct = trade["stop_pct"]
        if stop_pct <= 0:
            continue
        risk_amount_uncapped = TARGET_RISK_PCT / 100 * balance
        if liquidity_cap_pct is not None:
            market = market_for(trade["ticker"])
            adv = ADV_USD.get(market)
            max_notional = liquidity_cap_pct * adv
            notional_uncapped = risk_amount_uncapped / stop_pct
            notional_eff = min(notional_uncapped, max_notional)
            risk_amount = notional_eff * stop_pct
            if notional_eff < notional_uncapped - 1e-6:
                n_capped += 1
        else:
            risk_amount = risk_amount_uncapped
        pnl = trade["outcome_r"] * risk_amount
        balance += pnl
        n_trades += 1

        m = int(now // MONTH_SECONDS)
        month_snapshots[m] = balance

    # complete les mois sans trade avec le dernier solde connu (pas de trou dans la trajectoire)
    filled = []
    last = start_capital
    for m in range(max_month):
        if m in month_snapshots:
            last = month_snapshots[m]
        filled.append(last)

    return dict(final_balance=balance, n_trades=n_trades, n_capped=n_capped,
                capped_frac=n_capped / n_trades if n_trades else 0.0, month_trajectory=filled)


def run_scenario(n_sims, seed, target_duration_days, liquidity_cap_pct, label, start_capital=None):
    pop, sub_sorted, stop_pct_arr = load_population_with_stop_pct()
    alpha_post, beta_post = pdb.ALPHA_POST_B_PGP, pdb.BETA_POST_B_PGP
    rng_wr = random.Random(seed)
    rng_boot = random.Random(seed + 1)

    finals, capped_fracs, trajectories = [], [], []
    t0 = time.time()
    for _ in range(n_sims):
        wr_draw = rng_wr.betavariate(alpha_post, beta_post)
        trades, slot_arrivals = build_trades_with_stop_pct(pop, sub_sorted, stop_pct_arr, wr_draw,
                                                             random.Random(rng_boot.random()))
        res = simulate_one(trades, slot_arrivals, target_duration_days, liquidity_cap_pct, rng_boot,
                            alpha_post, beta_post, start_capital=start_capital)
        finals.append(res["final_balance"])
        capped_fracs.append(res["capped_frac"])
        trajectories.append(res["month_trajectory"])
    dt = time.time() - t0

    finals = np.array(finals)
    p10, p50, p90 = np.percentile(finals, [10, 50, 90])
    mean = finals.mean()
    max_len = max(len(t) for t in trajectories)
    traj_matrix = np.full((n_sims, max_len), np.nan)
    for i, t in enumerate(trajectories):
        traj_matrix[i, :len(t)] = t
    median_traj = np.nanmedian(traj_matrix, axis=0)

    print(f"[{label} dur={target_duration_days}j cap={liquidity_cap_pct}] n={n_sims} ({dt:.0f}s) "
          f"final: p10={p10:,.0f} p50={p50:,.0f} moy={mean:,.0f} p90={p90:,.0f} "
          f"| pct_trades_plafonnes moy={np.mean(capped_fracs)*100:.2f}%", flush=True)
    return dict(label=label, target_duration_days=target_duration_days, liquidity_cap_pct=liquidity_cap_pct,
                n=n_sims, p10=p10, p50=p50, mean=mean, p90=p90,
                capped_frac_mean=float(np.mean(capped_fracs)), median_trajectory=median_traj.tolist())


def main():
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 24680

    all_rows = []
    for duration_days, duration_label in [(365, "12mois"), (365 * 4, "48mois")]:
        print(f"\n{'='*100}\nDUREE={duration_label}\n{'='*100}", flush=True)
        row_unc = run_scenario(n_sims, seed, duration_days, None, f"non_plafonne_{duration_label}")
        all_rows.append(row_unc)
        for cap_pct, cap_label in [(0.01, "cap1pct"), (0.03, "cap3pct"), (0.05, "cap5pct")]:
            row = run_scenario(n_sims, seed, duration_days, cap_pct, f"{cap_label}_{duration_label}")
            all_rows.append(row)

    df = pd.DataFrame(all_rows)
    df.drop(columns=["median_trajectory"]).to_csv("chantier_liquidity_capacity_2026-08-23_summary.csv", index=False)
    print(f"\n{'='*100}\nSYNTHESE\n{'='*100}")
    print(df.drop(columns=["median_trajectory"]).to_string(index=False))

    import json
    with open("chantier_liquidity_capacity_2026-08-23_trajectories.json", "w") as f:
        json.dump({r["label"]: r["median_trajectory"] for r in all_rows}, f)


if __name__ == "__main__":
    main()

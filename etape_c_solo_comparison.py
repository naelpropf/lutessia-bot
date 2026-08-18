"""
Etape C : comparaison SOLO (1 compte, pas de flotte) de tous les formats
disponibles par firm, via engine_multiformat.py. Pour chaque format :
probabilite de financement, delai moyen, cout cumule jusqu'au financement
(echecs inclus, prix reel quand connu), taux de casse post-financement.

Ne conclut PAS sur "quel format est le meilleur" -- l'interaction flotte
(vitesse de refinancement, tresorerie) n'est testee qu'a l'Etape D. Un
format qui domine en solo peut etre moins bon combine aux autres (cf.
discussion utilisateur du 08/08).

FundedNext_StellarInstant est teste au palier 20 000$ (son plafond reel) --
PAS comparable directement aux autres FundedNext testes a 200 000$, note
explicitement dans le rapport.
"""
import random
import time

import pandas as pd

import robustness_5ers_risk_challenge as eng
from trailing_payoff_population import build_population_with_trailing
from monte_carlo_simulation import precompute_correlation_pairs
from real_cash_risk_year1_block_bootstrap import build_blocks
from reference_metrics_final import build_full_block_bootstrap_sequence

from engine_multiformat import FORMATS, make_acc_mf, process_trade_mf

DAY_SECONDS = 86400
BLOCK_MONTHS = 2
EVAL_RISK = 2.25
FUNDED_RISK = 2.75  # coherent avec FINAL_FLEET_RISK de la config verrouillee
N_SIMS = 300
SEED = 42

# Palier de reference par format : prix connu si disponible, sinon taille
# typique deja utilisee ailleurs dans le projet pour cette firm.
DEFAULT_PALIER_BY_FIRM = {"FTMO": 100000, "The5%ers": 100000, "Blueberry": 25000,
                          "GFT": 100000, "FundedNext": 200000}

# Overrides : formats dont le palier reel/pertinent differe du defaut de la
# firm (ex. FundedNext Stellar Instant plafonne a 20k$, pas 200k$).
PALIER_OVERRIDE = {"FundedNext_StellarInstant": 20000}


def palier_and_cost(fmt_key):
    fmt = FORMATS[fmt_key]
    known_prices = {p: c for p, c in fmt["price"].items() if c is not None}
    if fmt_key in PALIER_OVERRIDE:
        palier = PALIER_OVERRIDE[fmt_key]
        return palier, known_prices.get(palier)
    if not known_prices:
        return DEFAULT_PALIER_BY_FIRM[fmt["firm"]], None  # cout inconnu
    preferred = DEFAULT_PALIER_BY_FIRM[fmt["firm"]]
    palier = preferred if preferred in known_prices else sorted(known_prices.keys())[0]
    return palier, known_prices[palier]


def run_format_solo(fmt_key, palier, cost, blocks, block_seconds, target_duration, market_data, excluded_map,
                     n_sims, seed):
    fmt = FORMATS[fmt_key]
    cost_val = cost if cost is not None else 0.0
    rng_boot = random.Random(seed)
    results = []
    for sim in range(n_sims):
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng_boot, target_duration)

        acc = make_acc_mf(fmt, palier, cost=cost_val, active=True)
        state = {"reserve": 10_000_000.0, "total_breaks": 0, "ever_funded": False, "real_cash_paid": 0.0}
        first_funded_time = 0.0 if not fmt["phases"] else None
        if not fmt["phases"]:
            state["ever_funded"] = True
        cost_at_funding = None
        post_fund_breaks = 0
        was_ever_funded_flag = not fmt["phases"]

        for trade, now in zip(raw_trades, raw_slots):
            was_funded_before = acc["phase"] == "funded"
            breaks_before = state["total_breaks"]
            just_funded = process_trade_mf(acc, trade, now, fmt, state, EVAL_RISK if not was_funded_before else FUNDED_RISK,
                                            market_data, excluded_map, cost_override=cost_val)
            if just_funded and first_funded_time is None:
                first_funded_time = now
                cost_at_funding = acc["total_fees_paid"]
            if was_ever_funded_flag and was_funded_before and state["total_breaks"] > breaks_before:
                post_fund_breaks += 1
            if just_funded:
                was_ever_funded_flag = True

        results.append(dict(sim=sim, funded=first_funded_time is not None,
                             days_to_fund=(first_funded_time / DAY_SECONDS) if first_funded_time is not None else None,
                             cost_to_fund=cost_at_funding if fmt["phases"] else cost_val,
                             breaks_total=state["total_breaks"], post_fund_breaks=post_fund_breaks))
    return pd.DataFrame(results)


def main():
    t0 = time.time()
    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    market_data = eng.load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, eng.CORR_THRESHOLD)

    base_trades, base_slots = eng.build_flexible_population(pop, None, 1.0, False, random.Random(123))
    block_seconds = BLOCK_MONTHS * 30 * DAY_SECONDS
    blocks = build_blocks(base_trades, base_slots, block_seconds)
    target_duration = base_slots[-1]

    print(f"Population : {len(base_trades)} trades, horizon simule {target_duration/DAY_SECONDS:.0f}j, n={N_SIMS}/format.\n")

    rows = []
    for fmt_key, fmt in FORMATS.items():
        palier, cost = palier_and_cost(fmt_key)
        df = run_format_solo(fmt_key, palier, cost, blocks, block_seconds, target_duration, market_data, excluded_map,
                              n_sims=N_SIMS, seed=SEED)

        n_phases = len(fmt["phases"])
        dd_mode = fmt["phases"][0]["dd_max_mode"] if fmt["phases"] else fmt["funded"]["dd_max_mode"]
        pass_rate = df["funded"].mean() * 100
        mean_days = df.loc[df["funded"], "days_to_fund"].mean() if df["funded"].any() else float("nan")
        mean_cost = df.loc[df["funded"], "cost_to_fund"].mean() if df["funded"].any() else float("nan")
        mean_breaks = df["breaks_total"].mean()
        mean_post_breaks = df.loc[df["funded"], "post_fund_breaks"].mean() if df["funded"].any() else float("nan")

        rows.append(dict(firm=fmt["firm"], format=fmt_key, n_phases=n_phases, dd_mode=dd_mode,
                          palier=palier, cost_connu=cost is not None,
                          pass_rate_pct=pass_rate, mean_days_to_fund=mean_days,
                          mean_cost_to_fund=mean_cost, mean_breaks_pre_fund=mean_breaks,
                          mean_breaks_post_fund=mean_post_breaks,
                          copytrade_confirmed=fmt["copytrade_confirmed"]))
        print(f"[{fmt['firm']:10s}] {fmt_key:28s} palier={palier:>7,} phases={n_phases} dd={dd_mode:14s} "
              f"passage={pass_rate:5.1f}% delai={mean_days:6.1f}j cout_moy={mean_cost if mean_cost==mean_cost else float('nan'):>8.0f}$ "
              f"casse_post={mean_post_breaks:5.2f} ({time.time()-t0:.0f}s ecoules)")

    out = pd.DataFrame(rows)
    out.to_csv("etape_c_solo_comparison_results.csv", index=False)
    print(f"\nTermine en {time.time()-t0:.0f}s. Resultats -> etape_c_solo_comparison_results.csv")


if __name__ == "__main__":
    main()

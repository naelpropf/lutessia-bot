"""
Etape D -- premiere passe : recherche de la meilleure COMBINAISON DE FORMATS
entre firms au niveau flotte, via engine_multiformat.py.

PORTEE VOLONTAIREMENT SIMPLIFIEE (a lire avant d'interpreter les chiffres) :
  - Flotte active des le jour 0 (PAS de deblocage echelonne comme la config
    verrouillee actuelle -- ajouter cette mecanique developperait le nombre
    de variables en meme temps que le format, ce qui rendrait impossible de
    dire quel effet vient du format vs du timing de deblocage).
  - PAS de mecanisme "compte supplementaire" (extra-account growth) ni de
    croissance de palier par tier -- chaque compte reste a son palier de
    depart pour toute la simulation.
  - PAS de fiscalite (IS SASU).
  - Ces chiffres ne sont donc PAS comparables au chiffre verrouille actuel
    (5 794 566$/5 898 897$) -- c'est un outil de CRIBLAGE pour isoler l'effet
    du choix de format independamment du reste, pas une prevision finale.
    Integrer le format gagnant dans le moteur complet (deblocage echelonne +
    extra-comptes + fiscalite) est un travail separe, a faire une fois un
    candidat retenu ici.

Candidats par firm, filtres depuis l'Etape C (exclusion des formats
clairement domines ou aux donnees trop incertaines pour un criblage
serieux -- GFT Instant PRO [incoherence DD non resolue], Blueberry Instant
Lite [316 casses/horizon en solo, ecrase], FundedNext Stellar Instant
[plafonne 20k$, hors echelle du reste de la flotte]) :
  FTMO       : 2-Step Swing (actuel) vs 1-Step
  The5%ers   : High Stakes (actuel) vs Hyper Growth
  Blueberry  : Prime 2-Step (actuel, sous reserve de l'ambiguite Prime/
               standard non tranchee) vs Instant Elite
  GFT        : 2-Step GOAT (actuel) vs 1-Step vs Instant GOAT
  FundedNext : Stellar Lite (actuel) vs Stellar 1-Step

2x2x2x3x2 = 48 combinaisons, n=300/combo.
"""
import itertools
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
GFT_EVAL_RISK = 1.75
FUNDED_RISK = 2.75
SPLIT_FLAT = 0.80
N_SIMS = 300
SEED = 42
SNAPSHOT_DAYS = 180

# (n_accounts, palier) par firm -- palier de depart fixe, pas de tier growth.
FLEET_ACCOUNTS = {
    "FTMO": (2, 50000),
    "Fivers": (4, 100000),
    "Blueberry": (1, 25000),
    "GFT": (1, 50000),
    "FundedNext": (1, 200000),
}

CANDIDATES = {
    "FTMO": ["FTMO_2Step_Swing", "FTMO_1Step"],
    "Fivers": ["Fivers_HighStakes", "Fivers_HyperGrowth"],
    "Blueberry": ["Blueberry_Prime2Step", "Blueberry_InstantElite"],
    "GFT": ["GFT_2Step_GOAT", "GFT_1Step", "GFT_InstantGOAT"],
    "FundedNext": ["FundedNext_StellarLite", "FundedNext_Stellar1Step"],
}


def cost_at_palier(fmt, palier):
    return fmt["price"].get(palier) or 0.0


def run_combo(combo, blocks, block_seconds, target_duration, market_data, excluded_map, n_sims, seed):
    rng_boot = random.Random(seed)
    results = []
    for sim in range(n_sims):
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng_boot, target_duration)

        accounts = {}
        for firm, (n, palier) in FLEET_ACCOUNTS.items():
            fmt = FORMATS[combo[firm]]
            cost = cost_at_palier(fmt, palier)
            accounts[firm] = (fmt, [make_acc_mf(fmt, palier, cost=cost, active=True) for _ in range(n)])

        state = {"reserve": 0.0, "total_breaks": 0, "ever_funded": False, "real_cash_paid": 0.0}
        net_at_snapshot = None

        for trade, now in zip(raw_trades, raw_slots):
            for firm, (fmt, accs) in accounts.items():
                risk = GFT_EVAL_RISK if firm == "GFT" else EVAL_RISK
                for acc in accs:
                    r = FUNDED_RISK if acc["phase"] == "funded" else risk
                    cost = cost_at_palier(fmt, acc["palier"])
                    process_trade_mf(acc, trade, now, fmt, state, r, market_data, excluded_map,
                                      split_flat=SPLIT_FLAT, reserve_share=1.0, cost_override=cost)
            if net_at_snapshot is None and now >= SNAPSHOT_DAYS * DAY_SECONDS:
                net_at_snapshot = sum(a["total_funded_pnl"] - a["total_fees_paid"]
                                       for _, accs in accounts.values() for a in accs)

        final_net = sum(a["total_funded_pnl"] - a["total_fees_paid"] for _, accs in accounts.values() for a in accs)
        results.append(dict(sim=sim, final_net=final_net,
                             net_180d=net_at_snapshot if net_at_snapshot is not None else final_net,
                             total_breaks=state["total_breaks"]))
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

    combos = list(itertools.product(*[[(firm, k) for k in ks] for firm, ks in CANDIDATES.items()]))
    print(f"Population : {len(base_trades)} trades, horizon {target_duration/DAY_SECONDS:.0f}j, "
          f"{len(combos)} combinaisons, n={N_SIMS}/combo.\n")

    rows = []
    for i, combo_pairs in enumerate(combos):
        combo = dict(combo_pairs)
        df = run_combo(combo, blocks, block_seconds, target_duration, market_data, excluded_map,
                        n_sims=N_SIMS, seed=SEED)
        row = dict(combo, mean_final_net=df["final_net"].mean(),
                   mean_net_180d=df["net_180d"].mean(),
                   ruin_pct=(df["final_net"] < 0).mean() * 100,
                   mean_breaks=df["total_breaks"].mean())
        rows.append(row)
        print(f"[{i+1:2d}/{len(combos)}] {combo['FTMO']:18s} {combo['Fivers']:20s} {combo['Blueberry']:22s} "
              f"{combo['GFT']:16s} {combo['FundedNext']:24s} "
              f"net180j={row['mean_net_180d']:+9,.0f}$ net_final={row['mean_final_net']:+10,.0f}$ "
              f"ruine={row['ruin_pct']:4.1f}% ({time.time()-t0:.0f}s)")

    out = pd.DataFrame(rows).sort_values("mean_final_net", ascending=False)
    out.to_csv("etape_d_fleet_format_search_results.csv", index=False)
    print(f"\nTermine en {time.time()-t0:.0f}s. Resultats -> etape_d_fleet_format_search_results.csv")


if __name__ == "__main__":
    main()

"""
Etape B -- validation (sanity check) du nouveau moteur engine_multiformat.py.

Fait tourner process_trade_mf en solo (1 compte, pas de flotte) sur le format
ACTUELLEMENT utilise par le projet pour chaque firm, n=300, meme pool de
trades/bootstrap que les scripts de reference (reutilise build_population_
with_trailing / build_flexible_population / build_blocks / build_full_block_
bootstrap_sequence -- rien de reinvente).

But : verifier que le moteur tourne, que les taux de passage sont plausibles
(ni 0% ni 100%), et que DD statique vs trailing se comportent visiblement
differemment. PAS une comparaison au chiffre verrouille actuel (5 794 566$/
5 898 897$) -- attendu different puisque ce moteur utilise enfin les vraies
cibles par phase au lieu du flat 8%/4j global. Ce n'est pas un bug.
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
N_SIMS = 300
SEED = 42

# Format actuellement utilise par le projet, par firm, avec le palier de reference.
CURRENT_FORMATS = [
    ("FTMO", "FTMO_2Step_Swing", 100000),
    ("The5%ers", "Fivers_HighStakes", 100000),
    ("Blueberry", "Blueberry_Prime2Step", 25000),
    ("Blueberry", "Blueberry_2StepStandard", 25000),  # comparaison directe, ambiguite non tranchee
    ("GFT", "GFT_2Step_GOAT", 100000),
    ("FundedNext", "FundedNext_StellarLite", 200000),
]


def run_format(fmt_key, palier, blocks, block_seconds, target_duration, market_data, excluded_map,
               n_sims, seed):
    fmt = FORMATS[fmt_key]
    rng_boot = random.Random(seed)
    results = []
    for sim in range(n_sims):
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng_boot, target_duration)

        acc = make_acc_mf(fmt, palier, cost=0, active=True)
        state = {"reserve": 1_000_000.0, "total_breaks": 0, "ever_funded": False, "real_cash_paid": 0.0}
        # Instant funding (pas de phase d'evaluation) : deja "finance" des la
        # creation du compte, pas de transition a detecter via just_funded.
        first_funded_time = 0.0 if not fmt["phases"] else None
        if not fmt["phases"]:
            state["ever_funded"] = True

        for trade, now in zip(raw_trades, raw_slots):
            just_funded = process_trade_mf(acc, trade, now, fmt, state, EVAL_RISK,
                                            market_data, excluded_map, cost_override=0)
            if just_funded and first_funded_time is None:
                first_funded_time = now

        results.append(dict(sim=sim, funded=first_funded_time is not None,
                             days_to_fund=(first_funded_time / DAY_SECONDS) if first_funded_time is not None else None,
                             breaks=state["total_breaks"]))
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

    print(f"Population : {len(base_trades)} trades, horizon simule {target_duration/DAY_SECONDS:.0f}j.\n")

    rows = []
    for firm, fmt_key, palier in CURRENT_FORMATS:
        fmt = FORMATS[fmt_key]
        n_phases = len(fmt["phases"])
        dd_mode = fmt["phases"][0]["dd_max_mode"] if fmt["phases"] else fmt["funded"]["dd_max_mode"]

        df = run_format(fmt_key, palier, blocks, block_seconds, target_duration, market_data, excluded_map,
                         n_sims=N_SIMS, seed=SEED)

        pass_rate = df["funded"].mean() * 100
        mean_days = df.loc[df["funded"], "days_to_fund"].mean() if df["funded"].any() else float("nan")
        mean_breaks = df["breaks"].mean()
        row = dict(firm=firm, format=fmt_key, n_phases=n_phases, dd_mode_p1=dd_mode,
                   pass_rate_pct=pass_rate, mean_days_to_fund=mean_days, mean_breaks_before_fund=mean_breaks)
        rows.append(row)
        print(f"[{firm:12s}] {fmt_key:28s} phases={n_phases} dd_mode={dd_mode:14s} "
              f"passage={pass_rate:5.1f}% delai_moyen={mean_days:6.1f}j breaks_moy={mean_breaks:5.1f} "
              f"({time.time()-t0:.0f}s ecoules)")

    out = pd.DataFrame(rows)
    out.to_csv("engine_multiformat_smoke_test_results.csv", index=False)
    print(f"\nTermine en {time.time()-t0:.0f}s. Resultats -> engine_multiformat_smoke_test_results.csv")


if __name__ == "__main__":
    main()

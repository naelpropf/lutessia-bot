"""
Variante BLOCK BOOTSTRAP de real_cash_risk_year1_mc.py : au lieu de mélanger les
trades INDIVIDUELLEMENT sur les créneaux réels (bootstrap par permutation actuel --
détruit toute corrélation temporelle entre trades voisins), découpe l'historique en
blocs CONTIGUS de BLOCK_MONTHS mois consécutifs et rééchantillonne des BLOCS ENTIERS
avec remise pour reconstruire une trajectoire synthétique d'un an. Ça préserve le
regroupement temporel réel (une période volatile garde ses pertes ET ses gains
groupés ensemble, comme dans l'historique réel), que la permutation individuelle
étale artificiellement de façon uniforme dans le temps.

Réutilise TEL QUEL real_cash_risk_year1_mc.run_one_real_cash (la logique de compte --
challenge/casse/réserve/upgrade -- est inchangée, seule la construction de la séquence
de trades change) : chaque run construit une séquence synthétique (trades, slot_arrivals)
via block bootstrap, avec order=identité (les trades sont déjà dans le bon ordre
chronologique synthétique, pas besoin d'un 2e mélange qui détruirait la structure de
bloc qu'on vient de construire), puis appelle run_one_real_cash normalement.

Un seul tirage de blocs par run Monte Carlo, appliqué IDENTIQUEMENT aux 3 comptes
(même principe que le bootstrap par permutation existant : même signal répliqué en
copytrade).
"""
import random

import pandas as pd

from scaling_simulation import CORR_THRESHOLD, load_market_data
from monte_carlo_simulation import precompute_correlation_pairs, N_SIMULATIONS
from trailing_payoff_population import build_population_with_trailing, build_trades_trailing
from real_cash_risk_year1_mc import run_one_real_cash, RISK_PCT, N_ACCOUNTS, YEAR_SECONDS

BLOCK_MONTHS_VARIANTS = [1, 2, 3]
DAYS_PER_MONTH = 30.44  # mois moyen, cohérent avec les conventions déjà utilisées ailleurs (MONTH_SECONDS)


def build_blocks(trades, slot_arrivals, block_seconds):
    """Découpe (trades, slot_arrivals) en blocs contigus de block_seconds, depuis
    t=0. Chaque bloc : liste de (trade, offset_dans_le_bloc). Les blocs sans trade
    (période réelle sans signal) sont conservés dans le pool -- un vrai "trou"
    historique est une information valide, pas à exclure du tirage."""
    total_duration = slot_arrivals[-1]
    n_blocks = int(total_duration // block_seconds) + 1

    blocks = [[] for _ in range(n_blocks)]
    for trade, t in zip(trades, slot_arrivals):
        block_idx = int(t // block_seconds)
        offset = t - block_idx * block_seconds
        blocks[block_idx].append((trade, offset))

    return blocks


def build_block_bootstrap_sequence(blocks, block_seconds, rng, target_duration=YEAR_SECONDS):
    """Tire des blocs AVEC REMISE (ordre interne de chaque bloc préservé tel quel)
    jusqu'à couvrir au moins target_duration de trajectoire synthétique. Retourne
    (synthetic_trades, synthetic_slot_arrivals), triés par temps synthétique croissant
    (déjà garanti par construction : blocs placés bout à bout dans l'ordre du tirage)."""
    synthetic_trades = []
    synthetic_slots = []
    cursor = 0.0

    while cursor < target_duration:
        block = blocks[rng.randrange(len(blocks))]
        for trade, offset in block:
            synthetic_trades.append(trade)
            synthetic_slots.append(cursor + offset)
        cursor += block_seconds

    return synthetic_trades, synthetic_slots


def run_copytrade_real_cash_year1_block(blocks, block_seconds, risk_pct, market_data, excluded_map, rng):
    synthetic_trades, synthetic_slots = build_block_bootstrap_sequence(blocks, block_seconds, rng)
    identity_order = list(range(len(synthetic_trades)))
    per_account = [
        run_one_real_cash(synthetic_trades, synthetic_slots, risk_pct, market_data, excluded_map,
                           rng=None, order=identity_order)
        for _ in range(N_ACCOUNTS)
    ]
    return sum(per_account)


def summarize(results):
    results_sorted = sorted(results)
    n = len(results_sorted)
    mean_cash = sum(results_sorted) / n
    median_cash = results_sorted[n // 2]
    worst_case = results_sorted[-1]
    thresholds = {}
    for seuil in (1000, 2000, 3000):
        thresholds[seuil] = sum(1 for r in results if r > seuil) / n * 100
    return mean_cash, median_cash, worst_case, thresholds


def main():
    pop = build_population_with_trailing("fixed", 0.2, verbose=False)
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    sub, trades, slot_arrivals = build_trades_trailing(pop)
    tickers = sorted(set(t["ticker"] for t in trades))
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    print(f"Population : {len(trades)} trades, horizon total {slot_arrivals[-1]/86400/30.44:.1f} mois")

    # --- Référence déjà calculée (permutation) ---
    try:
        ref_df = pd.read_csv("real_cash_risk_year1_mc_detail.csv")
        ref_results = ref_df["real_cash_year1"].tolist()
        ref_mean, ref_median, ref_worst, ref_thr = summarize(ref_results)
        print(f"\n[Référence -- bootstrap PERMUTATION, déjà calculé] moyenne={ref_mean:,.0f}€ "
              f"médiane={ref_median:,.0f}€ pire={ref_worst:,.0f}€")
        for seuil, p in ref_thr.items():
            print(f"  P(>{seuil}€) = {p:.2f}%")
    except FileNotFoundError:
        ref_mean = ref_median = ref_worst = None
        ref_thr = {}
        print("[AVERTISSEMENT] real_cash_risk_year1_mc_detail.csv introuvable -- pas de comparaison directe.")

    rows = []
    all_detail = {}
    for block_months in BLOCK_MONTHS_VARIANTS:
        block_seconds = block_months * DAYS_PER_MONTH * 86400
        blocks = build_blocks(trades, slot_arrivals, block_seconds)
        n_nonempty = sum(1 for b in blocks if b)
        print(f"\n{'='*100}\nBLOCK BOOTSTRAP -- blocs de {block_months} mois "
              f"({len(blocks)} blocs au total, {n_nonempty} non vides)\n{'='*100}")

        rng = random.Random(42)
        results = [run_copytrade_real_cash_year1_block(blocks, block_seconds, RISK_PCT, market_data, excluded_map, rng)
                   for _ in range(N_SIMULATIONS)]
        mean_cash, median_cash, worst_case, thr = summarize(results)
        all_detail[block_months] = results

        print(f"Moyenne : {mean_cash:,.0f}€ | Médiane : {median_cash:,.0f}€ | Pire cas : {worst_case:,.0f}€")
        for seuil, p in thr.items():
            print(f"  P(>{seuil}€) = {p:.2f}%")

        if ref_mean is not None:
            print(f"\nDelta vs permutation : moyenne {mean_cash-ref_mean:+,.0f}€ | "
                  f"médiane {median_cash-ref_median:+,.0f}€ | pire cas {worst_case-ref_worst:+,.0f}€")

        rows.append({
            "block_months": block_months, "mean_cash": mean_cash, "median_cash": median_cash,
            "worst_case": worst_case, "p_gt_1000": thr[1000], "p_gt_2000": thr[2000], "p_gt_3000": thr[3000],
        })

    summary_df = pd.DataFrame(rows)
    summary_df.to_csv("real_cash_risk_year1_block_bootstrap_summary.csv", index=False)
    for block_months, results in all_detail.items():
        pd.DataFrame({"real_cash_year1": results}).to_csv(
            f"real_cash_risk_year1_block_bootstrap_{block_months}mo_detail.csv", index=False
        )

    print("\n" + "=" * 100)
    print("TABLEAU COMPARATIF FINAL")
    print("=" * 100)
    print(summary_df.to_string(index=False))
    print("\nRésumés enregistrés dans real_cash_risk_year1_block_bootstrap_summary.csv")
    return summary_df


if __name__ == "__main__":
    main()

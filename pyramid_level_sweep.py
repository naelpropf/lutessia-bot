"""
Balayage de 2-3 variantes d'espacement des paliers de pyramiding, après validation du
cas de base (+0.5R/+1R, cf. pyramid_backtest_summary.csv) qui a montré une
SOUS-PERFORMANCE nette du pyramiding vs baseline (structure A : ~4.16M€ moyen / 91
casses vs baseline ~10.34M€ / 41.4 casses -- cf. scratch_pyramid_ev_check.py pour le
diagnostic : les unités ajoutées captent structurellement moins de R que l'unité
initiale -- elles entrent plus tard, il leur reste moins de chemin jusqu'à la même
sortie -- et restent exposées à une perte quasi complète sur les ~36% de trades qui
touchent +0.5R puis reversent quand même malgré un winrate conditionnel nettement
supérieur, 63.9% vs 37.3% non conditionnel).

Variantes testées :
  - +0.75R / +1.5R (2 paliers, espacement plus large -- moins de faux départs
    pyramidés, mais aussi moins de trades qui déclenchent les ajouts)
  - +0.5R / +1R / +1.5R (3 paliers, structure B dégressive 50/25/12.5%)

Méthodologie de robustesse -- même principe que le balayage qui a validé le trailing
0.2xSL (split chronologique 1ère/2e moitié + sensibilité au retrait du trade le plus
contributeur) : d'abord un tri rapide sur l'EV BRUTE en R (pas de Monte Carlo, pas de
sizing $), puis le Monte Carlo flotte complet (2000 runs, même protocole que
pyramid_fleet_test.py) sur TOUTES les variantes pour une comparaison directe et
définitive avec le cas de base et la baseline.
"""
import pandas as pd

from pyramid_payoff_population import build_population_with_pyramid
from pyramid_fleet_test import run_structure
from scaling_simulation import load_market_data

VARIANTS = {
    "0.75R_1.5R": {"levels": [0.75, 1.5], "A": [1.0, 1.0], "B": [0.5, 0.25]},
    "0.5R_1R_1.5R": {"levels": [0.5, 1.0, 1.5], "A": [1.0, 1.0, 1.0], "B": [0.5, 0.25, 0.125]},
}


def weighted_r(units):
    return sum(u["fraction"] * u["exit_r"] for u in units)


def raw_ev_report(pop, label):
    """EV brute en R (pas de Monte Carlo, pas de sizing $/faisabilité) -- rapide, pour un
    premier diagnostic de robustesse avant le Monte Carlo flotte complet."""
    pop = pop.sort_values("date_creation").reset_index(drop=True)
    weighted = pop["units"].apply(weighted_r)
    baseline_ev = pop["r_realiste"]

    mid = len(pop) // 2
    delta_first = weighted.iloc[:mid].mean() - baseline_ev.iloc[:mid].mean()
    delta_second = weighted.iloc[mid:].mean() - baseline_ev.iloc[mid:].mean()

    contrib = weighted - baseline_ev
    idx_max_contrib = contrib.abs().idxmax()
    ev_without_best = weighted.drop(idx_max_contrib).mean() - baseline_ev.drop(idx_max_contrib).mean()

    row = {
        "variant": label,
        "pyramid_ev_r": weighted.mean(), "baseline_ev_r": baseline_ev.mean(),
        "delta_ev_r": weighted.mean() - baseline_ev.mean(),
        "delta_1st_half": delta_first, "delta_2nd_half": delta_second,
        "delta_without_top_contributor": ev_without_best,
    }
    print(f"\n--- {label} (diagnostic EV brute, sans Monte Carlo) ---")
    print(f"EV pondérée (R) : {row['pyramid_ev_r']:+.4f} (baseline {row['baseline_ev_r']:+.4f}, "
          f"delta {row['delta_ev_r']:+.4f})")
    print(f"Delta 1ère moitié chronologique : {delta_first:+.4f} | 2e moitié : {delta_second:+.4f}")
    print(f"Delta sans le trade le plus contributeur (ticker={pop.loc[idx_max_contrib, 'ticker']}, "
          f"date={pop.loc[idx_max_contrib, 'date_creation']}, contribution={contrib[idx_max_contrib]:+.3f}R) : "
          f"{ev_without_best:+.4f}")
    return row


def main():
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)

    quick_rows = []
    fleet_rows = []
    for variant_label, cfg in VARIANTS.items():
        levels = cfg["levels"]
        for struct_label in ("A", "B"):
            fractions = cfg[struct_label]
            full_label = f"{variant_label}_{struct_label}"

            pop, _ = build_population_with_pyramid(levels, fractions, verbose=True)
            quick_rows.append(raw_ev_report(pop, full_label))

            fleet_rows.append(run_structure(full_label, levels, fractions, corr_matrix, market_data))

    quick_df = pd.DataFrame(quick_rows)
    quick_df.to_csv("pyramid_level_sweep_quick_ev.csv", index=False)

    fleet_df = pd.DataFrame(fleet_rows)
    try:
        base_case = pd.read_csv("pyramid_backtest_summary.csv")
        fleet_df = pd.concat([base_case, fleet_df], ignore_index=True)
    except FileNotFoundError:
        pass
    fleet_df.to_csv("pyramid_level_sweep_summary.csv", index=False)

    print("\n" + "=" * 100)
    print("TRI RAPIDE (EV brute en R, sans Monte Carlo) -- toutes variantes")
    print("=" * 100)
    print(quick_df.to_string(index=False))

    print("\n" + "=" * 100)
    print("TABLEAU COMPARATIF FINAL -- Monte Carlo flotte complet, baseline + cas de base + balayage")
    print("=" * 100)
    print(fleet_df.to_string(index=False))
    print("\nRésumés enregistrés dans pyramid_level_sweep_quick_ev.csv et pyramid_level_sweep_summary.csv")
    return quick_df, fleet_df


if __name__ == "__main__":
    main()

"""Etape 0 (investigation MAX_POSITIONS, 2026-08-19) : replay chronologique
1-compte IDENTIQUE a la methode de section1_replay() (chantier_position_cap_
2026-08-15.py:86-181, cf. registre_strategie_trading.md S2.28), applique a
la population B Config 2 (metaux+forex/indices, 1505 trades) au lieu de la
population A seule (n=631 a l'epoque de S2.28). Objectif : verifier si le
verdict S2.28 (cap=3 rarement contraignant, signaux bloques a faible EV)
tient toujours sous le rythme B Config 2 (171,6% de A)."""
import pandas as pd

from monte_carlo_simulation import precompute_correlation_pairs
from scaling_simulation import CORR_THRESHOLD
import robustness_5ers_risk_challenge as eng

CORR_TH = CORR_THRESHOLD  # 0.80, identique a S2.28/adopte projet


def section1_replay(pop, label):
    pop = pop.sort_values("date_creation").reset_index(drop=True)
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)

    open_positions = []
    rows = []
    for _, row in pop.iterrows():
        now = row["date_creation"]
        close_time = row["resolution_time_est"]
        ticker = row["ticker"]
        rr = row["rr_tp1"]
        r = row["r_trailing"]

        open_positions = [(t, c, x) for (t, c, x) in open_positions if c > now]

        blocked_reason = None
        weakest_open_rr = min((x for (_, _, x) in open_positions), default=float("nan"))
        if len(open_positions) >= eng.MAX_POSITIONS:
            blocked_reason = "cap_position"
        elif any(t in excluded_map[ticker] for (t, _, _) in open_positions):
            blocked_reason = "correlation"

        rows.append({"date_creation": now, "ticker": ticker, "rr_tp1": rr, "r_trailing": r,
                      "n_open_at_signal": len(open_positions), "blocked_reason": blocked_reason,
                      "weakest_open_rr_at_signal": weakest_open_rr})

        if blocked_reason is None:
            open_positions.append((ticker, close_time, rr))

    df = pd.DataFrame(rows)
    n = len(df)
    taken = df[df["blocked_reason"].isna()]
    cap = df[df["blocked_reason"] == "cap_position"]
    corr = df[df["blocked_reason"] == "correlation"]

    def fmt_block(lbl, sub):
        if len(sub) == 0:
            print(f"  {lbl:16s}:    0 ( 0.0%)")
            return
        print(f"  {lbl:16s}: {len(sub):4d} ({len(sub) / n * 100:5.1f}%) | "
              f"R_trailing moyen={sub['r_trailing'].mean():+.3f} | "
              f"winrate={(sub['r_trailing'] > 0).mean() * 100:5.1f}% | "
              f"RR(rr_tp1) moyen={sub['rr_tp1'].mean():.2f} | RR median={sub['rr_tp1'].median():.2f}")

    print(f"\n{'='*78}\n{label} -- replay 1-compte (n={n}, cap={eng.MAX_POSITIONS}, corr_th={CORR_TH})\n{'='*78}")
    fmt_block("Pris", taken)
    fmt_block("Bloque (cap)", cap)
    fmt_block("Bloque (correl)", corr)
    if len(cap):
        print(f"\n  RR(rr_tp1) bloques-cap : min={cap['rr_tp1'].min():.2f} median={cap['rr_tp1'].median():.2f} "
              f"max={cap['rr_tp1'].max():.2f}")
        print(f"  R cumule laisse sur la table (cap seul) = {cap['r_trailing'].sum():+.2f}R sur {len(cap)} signaux "
              f"({len(cap)/n*100:.1f}% de la population)")
        # distribution mensuelle du blocage-cap (rythme -- utile pour situer si c'est concentre ou diffus)
        cap_by_month = cap.assign(month=cap["date_creation"].dt.to_period("M")).groupby("month").size()
        print(f"  Mois avec au moins 1 blocage-cap : {(cap_by_month > 0).sum()} mois sur "
              f"{pop['date_creation'].dt.to_period('M').nunique()} mois couverts. "
              f"Max blocages/mois={cap_by_month.max() if len(cap_by_month) else 0}")
    if len(corr):
        print(f"  R cumule laisse sur la table (correlation seule) = {corr['r_trailing'].sum():+.2f}R sur {len(corr)} signaux")
    return df


if __name__ == "__main__":
    print("[verif] MAX_POSITIONS =", eng.MAX_POSITIONS, "(scaling_simulation.py:47, importe via robustness_5ers_risk_challenge)")

    # --- Reference A (reproduction exacte S2.28 pour verifier la methode, population actuelle) ---
    from trailing_payoff_population import build_population_with_trailing
    pop_A = build_population_with_trailing("fixed", 0.15, min_rr=1.35, verbose=False)
    section1_replay(pop_A, "STRATEGIE A (reference S2.28, population actuelle post forex-only-fix)")

    # --- Population B Config 2 (forex/indices + metaux, 1505 trades) ---
    pop_B = pd.read_csv("chantier_gold_silver_pop_B_config0_2026-08-19.csv")
    pop_B["date_creation"] = pd.to_datetime(pop_B["date_creation"])
    pop_B["resolution_time_est"] = pd.to_datetime(pop_B["resolution_time_est"])
    section1_replay(pop_B, "STRATEGIE B Config2 (metaux+forex/indices, 1505 trades)")

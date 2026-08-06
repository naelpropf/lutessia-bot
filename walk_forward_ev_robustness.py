"""
Vérifie si l'EV supérieure de la période de test (walk-forward, split chronologique
par NOMBRE de trades -- même convention que rr_threshold_test.py "1ère/2e moitié")
est portée par quelques trades exceptionnels (R élevé) ou par un edge homogène.
Retire les 3 et 5 meilleurs trades de la période de test et recalcule l'EV -- si elle
reste nettement au-dessus de l'entraînement, edge réel ; si elle s'effondre vers le
niveau d'entraînement, l'écart initial était surtout porté par quelques gros gains.

Deux splits testés : 60/40 (comme le walk-forward de référence) et 50/50 (test de
stabilité au choix du point de coupure).

Payoff : r_trailing (convention verrouillée, réaliste + trailing 0.2xSL), sur la
population de référence (rr_tp1>=1.5, 472 trades).
"""
import pandas as pd

POP_PATH = "trailing_realistic_payoff_detail.csv"


def load_sorted_pop():
    df = pd.read_csv(POP_PATH)
    df["date_creation"] = pd.to_datetime(df["date_creation"])
    return df.sort_values("date_creation").reset_index(drop=True)


def report_split(df, train_frac, label):
    n = len(df)
    cut = int(round(n * train_frac))
    train = df.iloc[:cut]
    test = df.iloc[cut:].copy()

    print(f"\n{'='*100}")
    print(f"SPLIT {label} ({train_frac*100:.0f}/{(1-train_frac)*100:.0f}) -- coupure au {test['date_creation'].iloc[0]}")
    print(f"{'='*100}")
    print(f"Entraînement : n={len(train)} ({train['date_creation'].min()} -> {train['date_creation'].max()}) "
          f"| EV = {train['r_trailing'].mean():+.3f}R")
    print(f"Test          : n={len(test)} ({test['date_creation'].min()} -> {test['date_creation'].max()}) "
          f"| EV = {test['r_trailing'].mean():+.3f}R")

    train_ev = train["r_trailing"].mean()
    test_sorted = test.sort_values("r_trailing", ascending=False)

    print(f"\nMeilleurs trades de la période de test :")
    for _, row in test_sorted.head(5).iterrows():
        print(f"  {row['ticker']:<8} {row['date_creation']} : R = {row['r_trailing']:+.2f}")

    for k in [3, 5]:
        remaining = test_sorted.iloc[k:]
        ev_wo = remaining["r_trailing"].mean()
        removed_sum = test_sorted.iloc[:k]["r_trailing"].sum()
        print(f"\nAprès retrait des {k} meilleurs trades (n={len(remaining)}) :")
        print(f"  EV test sans ces {k} trades = {ev_wo:+.3f}R (contre {test['r_trailing'].mean():+.3f}R avec, "
              f"et {train_ev:+.3f}R en entraînement)")
        print(f"  Somme R retirée : {removed_sum:+.2f} (soit {removed_sum/test['r_trailing'].sum()*100:.1f}% de la "
              f"somme totale des R de test)")
        gap_before = test['r_trailing'].mean() - train_ev
        gap_after = ev_wo - train_ev
        pct_gap_remaining = gap_after / gap_before * 100 if gap_before != 0 else float('nan')
        print(f"  Écart test-train : {gap_before:+.3f}R avant retrait -> {gap_after:+.3f}R après "
              f"({pct_gap_remaining:.0f}% de l'écart initial subsiste)")
        if ev_wo < train_ev * 1.3 and abs(ev_wo - train_ev) < 0.3:
            print(f"  -> Effondrement vers le niveau d'entraînement : l'écart initial était surtout porté par ces {k} trades.")
        elif ev_wo > train_ev:
            print(f"  -> EV test reste au-dessus de l'entraînement même sans ces {k} trades : edge plus homogène.")


def main():
    df = load_sorted_pop()
    print(f"Population totale : {len(df)} trades ({df['date_creation'].min()} -> {df['date_creation'].max()})")

    report_split(df, 0.60, "RÉFÉRENCE")
    report_split(df, 0.50, "ALTERNATIF")


if __name__ == "__main__":
    main()

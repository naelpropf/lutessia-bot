"""chantier_diagnostic_chop_bloc1bloc2_2026-08-23.py

Analyse EXPLORATOIRE/DIAGNOSTIQUE (pas un test de filtre a adopter, demande
utilisateur session 23/08) : le creux relatif de bloc2 (winrate 43,12%/EV
+1,35R vs bloc1 54,29%/+2,16R, bloc3 50,34%/+1,65R, bloc4 47,92%/+1,58R,
tous sains post-fix r_trailing) a-t-il une signature detectable a l'entree
du trade (confluence EMA+MACD 2 horizons, deja calculee par piste 2), ou
est-il diffus ?

Reutilise directement chantier_piste2_signaux_2026-08-21.csv (571 trades
forex/indices B_tradable_pgp, r_trailing corrige, confluence_n 0-4 deja
calculee par chantier_piste2_confluence_multihorizon_2026-08-21.py sur
donnees completes) -- pas de recalcul de bougies necessaire.

Etapes (cf. demande) :
1. deja fait (fichier source) -- pas de seuil applique.
2. distribution confluence_n gagnants vs perdants, bloc1 et bloc2 separement,
   Mann-Whitney U (ordinal, pas de moyenne).
3. moyenne mobile mensuelle de confluence_n sur bloc1+bloc2.
4. comparaison aux 4 fenetres macro deja etudiees.
5. winrate/EV des fenetres de desaccord identifiees vs reste bloc1+bloc2.
"""
import numpy as np
import pandas as pd
from scipy import stats as sps

WINDOWS = [
    ("SVB", "2023-03-08", "2023-03-24"),
    ("dette_US_fitch", "2023-05-15", "2023-08-15"),
    ("ukraine_petrole", "2022-02-24", "2022-04-15"),
    ("israel_hamas", "2023-10-07", "2023-11-15"),
]


def load():
    df = pd.read_csv("chantier_piste2_signaux_2026-08-21.csv")
    df["date_creation"] = pd.to_datetime(df["date_creation"])
    return df


def etape2(df):
    print(f"\n{'='*90}\nETAPE 2 -- distribution confluence_n gagnants vs perdants (Mann-Whitney U)\n{'='*90}")
    for bl in ("bloc1", "bloc2"):
        sub = df[(df["bloc"] == bl) & df["confluence_n"].notna()]
        wins = sub[sub["r_trailing"] > 0]["confluence_n"]
        losses = sub[sub["r_trailing"] <= 0]["confluence_n"]
        print(f"\n  {bl} (n={len(sub)}, wins={len(wins)}, losses={len(losses)})")
        print(f"    distribution confluence_n gagnants : {wins.value_counts().sort_index().to_dict()}")
        print(f"    distribution confluence_n perdants  : {losses.value_counts().sort_index().to_dict()}")
        print(f"    moyenne gagnants={wins.mean():.3f}  moyenne perdants={losses.mean():.3f}")
        if len(wins) > 0 and len(losses) > 0:
            u, p = sps.mannwhitneyu(wins, losses, alternative="two-sided")
            print(f"    Mann-Whitney U : U={u:.1f}  p={p:.4f}")
        ct = pd.crosstab(sub["confluence_n"], sub["r_trailing"] > 0)
        if ct.shape[0] > 1 and ct.shape[1] > 1:
            chi2, pchi, dof, _ = sps.chi2_contingency(ct)
            print(f"    Chi2 independance (confluence_n x win/loss) : chi2={chi2:.3f} dof={dof} p={pchi:.4f}")
            print(f"    table :\n{ct}")


def etape3(df):
    print(f"\n{'='*90}\nETAPE 3 -- confluence_n moyenne par mois, bloc1+bloc2 (2021-04 -> 2023-12)\n{'='*90}")
    sub = df[df["bloc"].isin(["bloc1", "bloc2"]) & df["confluence_n"].notna()].copy()
    sub["month"] = sub["date_creation"].dt.to_period("M")
    monthly = sub.groupby("month").agg(n=("confluence_n", "size"), conf_mean=("confluence_n", "mean"),
                                        winrate=("r_trailing", lambda s: 100 * (s > 0).mean()),
                                        ev=("r_trailing", "mean")).reset_index()
    overall_mean = sub["confluence_n"].mean()
    overall_std = sub["confluence_n"].std(ddof=1)
    print(f"  moyenne globale confluence_n (bloc1+bloc2) = {overall_mean:.3f} (std={overall_std:.3f})")
    print(f"  seuil 'desaccord eleve' explo = moyenne mensuelle < {overall_mean - overall_std:.3f} (1 std sous la moyenne globale)\n")
    for _, r in monthly.iterrows():
        flag = " <-- DESACCORD ELEVE" if r["conf_mean"] < (overall_mean - overall_std) and r["n"] >= 3 else ""
        print(f"    {r['month']}  n={r['n']:3.0f}  conf_moy={r['conf_mean']:.2f}  winrate={r['winrate']:5.1f}%  EV={r['ev']:+.3f}R{flag}")
    return monthly, overall_mean, overall_std


def etape4(monthly, overall_mean, overall_std):
    print(f"\n{'='*90}\nETAPE 4 -- mois de desaccord eleve vs fenetres macro connues\n{'='*90}")
    low_months = monthly[(monthly["conf_mean"] < (overall_mean - overall_std)) & (monthly["n"] >= 3)]
    print(f"  {len(low_months)} mois identifies en desaccord eleve (n>=3, conf_moy < {overall_mean-overall_std:.2f}) :")
    for _, r in low_months.iterrows():
        m_start = r["month"].start_time
        m_end = r["month"].end_time
        overlaps = []
        for name, s, e in WINDOWS:
            s_ts, e_ts = pd.Timestamp(s), pd.Timestamp(e)
            if m_start <= e_ts and m_end >= s_ts:
                overlaps.append(name)
        print(f"    {r['month']} (n={r['n']:.0f}, conf_moy={r['conf_mean']:.2f}) -- chevauche : {overlaps if overlaps else 'AUCUNE fenetre macro connue'}")
    return low_months


def etape5(df, low_months):
    print(f"\n{'='*90}\nETAPE 5 -- winrate/EV des mois de desaccord eleve vs reste bloc1+bloc2\n{'='*90}")
    sub = df[df["bloc"].isin(["bloc1", "bloc2"]) & df["confluence_n"].notna()].copy()
    sub["month"] = sub["date_creation"].dt.to_period("M")

    def stats_block(d, label):
        n = len(d)
        wins = int((d["r_trailing"] > 0).sum())
        ev = d["r_trailing"].mean()
        se = d["r_trailing"].std(ddof=1) / np.sqrt(n) if n > 1 else float("nan")
        print(f"    {label:35s} n={n:4d} wins={wins:4d} winrate={100*wins/n if n else float('nan'):6.2f}% EV={ev:+.4f}R se={se:.4f}")
        return d["r_trailing"]

    if len(low_months) == 0:
        print("  Aucun mois de desaccord eleve identifie (seuil 1 std) -- pas de comparaison mensuelle possible.")
    else:
        flagged_months = set(low_months["month"])
        in_low = sub[sub["month"].isin(flagged_months)]
        out_low = sub[~sub["month"].isin(flagged_months)]
        r_in = stats_block(in_low, "trades DANS mois desaccord eleve")
        r_out = stats_block(out_low, "trades HORS mois desaccord eleve")
        if len(r_in) > 1 and len(r_out) > 1:
            t, p = sps.ttest_ind(r_in, r_out, equal_var=False)
            print(f"    Welch t-test EV in vs out : t={t:.3f} p={p:.4f}")
    # egalement : comparaison directe confluence-based (sans passer par les mois),
    # au niveau trade, sur toute confluence_n<=1 (0 ou 1 signal d'accord/4) comme
    # proxy exploratoire de "desaccord fort au niveau trade" (PAS un seuil de filtre)
    print("\n  Complement (niveau trade, pas mensuel) : confluence_n<=1/4 vs >=2/4, bloc1+bloc2")
    lo = sub[sub["confluence_n"] <= 1]
    hi = sub[sub["confluence_n"] >= 2]
    r_lo = stats_block(lo, "confluence_n<=1/4")
    r_hi = stats_block(hi, "confluence_n>=2/4")
    if len(r_lo) > 1 and len(r_hi) > 1:
        t, p = sps.ttest_ind(r_lo, r_hi, equal_var=False)
        print(f"    Welch t-test EV <=1/4 vs >=2/4 : t={t:.3f} p={p:.4f}")


def main():
    df = load()
    etape2(df)
    monthly, mean_, std_ = etape3(df)
    low_months = etape4(monthly, mean_, std_)
    etape5(df, low_months)


if __name__ == "__main__":
    main()

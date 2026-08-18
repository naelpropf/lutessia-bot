"""
Partie B : le rejeu 1-compte (missed_signals_replay.py) donnait une borne
HAUTE du cout d'opportunite de la regle de correlation (+158.86R sur 101/646
signaux). Ici, rejeu sur la structure COMPLETE (9 comptes, 5 firms -- meme
logique EXACTE que account_router.eligible_accounts/scaling_simulation.
correlated, deja utilisee par tout le moteur Monte Carlo du projet ou chaque
compte decide independamment via excluded_map) pour mesurer le cout NET reel :
un signal bloque sur UN compte est-il quand meme capture par la flotte via un
AUTRE compte disponible, ou reellement perdu (aucun des 9 comptes eligible) ?

Structure : GROUP_DEFS n_accounts (Blueberry=1, FTMO=2, Fivers=4, GFT=1,
FundedNext=1 = 9 comptes), tous actifs simultanement des le depart (hypothese
"flotte complete", demandee explicitement -- ignore le ramp de sequencement
pour isoler la question posee : la redondance inter-comptes recupere-t-elle
les signaux bloques individuellement ?).
"""
import pandas as pd

from scaling_simulation import CORR_THRESHOLD, MAX_POSITIONS, correlated
from point123_startingfirm_optimization import GROUP_DEFS
from trailing_payoff_population import build_population_with_trailing


def main():
    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    pop = pop.sort_values("date_creation").reset_index(drop=True)
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)

    REAL_FLEET_GROUPS = ("Blueberry", "FTMO", "Fivers", "GFT", "FundedNext")  # exclut "Fivers1", variante de
    # comparaison 1-compte ajoutee par point123_startingfirm_optimization.py, PAS un groupe de la vraie flotte
    accounts = []
    for gname in REAL_FLEET_GROUPS:
        gdef = GROUP_DEFS[gname]
        for i in range(gdef["n_accounts"]):
            accounts.append({"id": f"{gname}_{i+1}", "group": gname, "open_positions": []})
    print(f"Flotte simulee : {len(accounts)} comptes -- {[a['id'] for a in accounts]}")

    rows = []
    for _, row in pop.iterrows():
        now = row["date_creation"]
        close_time = row["resolution_time_est"]
        ticker = row["ticker"]
        r = row["r_trailing"] if row["statut_final"] == "OBJECTIF ATTEINT" else -1.0

        n_eligible = 0
        n_would_be_blocked_by_cap = 0
        n_would_be_blocked_by_corr = 0
        for acc in accounts:
            acc["open_positions"] = [(t, c) for (t, c) in acc["open_positions"] if c > now]
            if len(acc["open_positions"]) >= MAX_POSITIONS:
                n_would_be_blocked_by_cap += 1
                continue
            if any(correlated(ticker, t, corr_matrix) for (t, _) in acc["open_positions"]):
                n_would_be_blocked_by_corr += 1
                continue
            n_eligible += 1
            acc["open_positions"].append((ticker, close_time))

        rows.append({"date_creation": now, "ticker": ticker, "r_trailing": r,
                      "n_accounts_eligible": n_eligible, "n_blocked_cap": n_would_be_blocked_by_cap,
                      "n_blocked_corr": n_would_be_blocked_by_corr, "n_accounts_total": len(accounts)})

    df = pd.DataFrame(rows)
    df.to_csv("correlation_fleet_replay_detail.csv", index=False)

    n = len(df)
    fully_lost = df[df["n_accounts_eligible"] == 0]
    at_least_one = df[df["n_accounts_eligible"] > 0]
    had_some_corr_block = df[df["n_blocked_corr"] > 0]
    recovered = had_some_corr_block[had_some_corr_block["n_accounts_eligible"] > 0]
    truly_lost_due_to_corr = had_some_corr_block[had_some_corr_block["n_accounts_eligible"] == 0]

    print(f"\nSignaux total : {n}")
    print(f"Signaux avec AU MOINS 1 compte bloque par correlation sur au moins 1 compte : {len(had_some_corr_block)} ({len(had_some_corr_block)/n*100:.1f}%)")
    print(f"  -> dont recuperes par au moins un AUTRE compte (flotte capture quand meme) : {len(recovered)} ({len(recovered)/max(1,len(had_some_corr_block))*100:.1f}% de ce sous-groupe)")
    print(f"  -> dont REELLEMENT perdus (0 compte eligible sur les 9)                    : {len(truly_lost_due_to_corr)} ({len(truly_lost_due_to_corr)/max(1,len(had_some_corr_block))*100:.1f}% de ce sous-groupe)")

    print(f"\nSignaux totalement perdus (0/9 comptes eligibles, toute raison confondue) : {len(fully_lost)} ({len(fully_lost)/n*100:.1f}%)")
    if len(fully_lost):
        print(f"  R moyen qu'ils auraient fait : {fully_lost['r_trailing'].mean():+.3f} | R cumule perdu : {fully_lost['r_trailing'].sum():+.2f}R")

    r_lost_pure_corr = truly_lost_due_to_corr["r_trailing"].sum()
    print(f"\n=== COUT D'OPPORTUNITE NET REEL (correlation, echelle flotte) ===")
    print(f"R cumule reellement perdu a cause de la regle de correlation (0/9 comptes eligibles ET un blocage corr y contribue) : {r_lost_pure_corr:+.2f}R sur {len(truly_lost_due_to_corr)} signaux")
    print(f"Rappel borne haute (1 seul compte)                                                                                 : +158.86R sur 101 signaux")
    print(f"Nombre moyen de comptes eligibles par signal (sur 9)                                                              : {df['n_accounts_eligible'].mean():.2f}")


if __name__ == "__main__":
    main()

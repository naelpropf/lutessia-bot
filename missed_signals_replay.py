"""
Rejoue la population REELLE (ordre chronologique reel, PAS bootstrap) a travers
EXACTEMENT la meme logique de routage que account_router.py (cap=MAX_POSITIONS
par compte, exclusion correlation>=CORR_THRESHOLD ou JPY-JPY) pour quantifier
combien de signaux auraient ete bloques, et surtout -- ce qu'aucun log de
production ne peut donner puisque trades_reels.csv est vide -- QUEL R ils
auraient rapporte, puisque leur issue est deja connue dans la population
historique (r_trailing).

Limite explicite : ne couvre QUE les 2 categories mecaniques (cap de position,
correlation) -- pas les incidents techniques (rate-limit, verrou mono-instance,
erreur MT5), qui necessitent des logs d'execution reels inexistants a ce jour.

Hypothese de structure : 1 compte generique (comme le modele de risque
scaling_simulation le fait), MAX_POSITIONS=3, CORR_THRESHOLD=0.6+JPY-JPY,
positions fermees a resolution_time_est (duree reelle verifiee ou mediane par
defaut, deja la colonne utilisee partout dans le projet).
"""
import pandas as pd

from scaling_simulation import CORR_THRESHOLD, MAX_POSITIONS, correlated
from trailing_payoff_population import build_population_with_trailing


def main():
    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    pop = pop.sort_values("date_creation").reset_index(drop=True)
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)

    open_positions = []  # list of (ticker, close_time)
    rows = []
    for _, row in pop.iterrows():
        now = row["date_creation"]
        close_time = row["resolution_time_est"]
        ticker = row["ticker"]
        r = row["r_trailing"] if row["statut_final"] == "OBJECTIF ATTEINT" else -1.0

        open_positions = [(t, c) for (t, c) in open_positions if c > now]

        blocked_reason = None
        if len(open_positions) >= MAX_POSITIONS:
            blocked_reason = "cap_position"
        elif any(correlated(ticker, t, corr_matrix) for (t, _) in open_positions):
            blocked_reason = "correlation"

        rows.append({"date_creation": now, "ticker": ticker, "r_trailing": r,
                      "n_open_at_signal": len(open_positions), "blocked_reason": blocked_reason})

        if blocked_reason is None:
            open_positions.append((ticker, close_time))
        # NB : un signal bloque n'ouvre PAS de position -- ne consomme pas de slot,
        # coherent avec account_router.select_account (retourne None, aucun ordre envoye)

    df = pd.DataFrame(rows)
    df.to_csv("missed_signals_replay_detail.csv", index=False)

    n = len(df)
    taken = df[df["blocked_reason"].isna()]
    cap = df[df["blocked_reason"] == "cap_position"]
    corr = df[df["blocked_reason"] == "correlation"]

    print(f"Population rejouee (ordre chronologique reel, 1 compte) : n={n}")
    print(f"  Pris            : {len(taken):4d} ({len(taken)/n*100:5.1f}%) | R moyen={taken['r_trailing'].mean():+.3f} | winrate={(taken['r_trailing']>0).mean()*100:.1f}%")
    print(f"  Bloque (cap)    : {len(cap):4d} ({len(cap)/n*100:5.1f}%) | R moyen qu'ils AURAIENT fait={cap['r_trailing'].mean():+.3f} | winrate qu'ils AURAIENT fait={(cap['r_trailing']>0).mean()*100:.1f}%")
    print(f"  Bloque (correl) : {len(corr):4d} ({len(corr)/n*100:5.1f}%) | R moyen qu'ils AURAIENT fait={corr['r_trailing'].mean():+.3f} | winrate qu'ils AURAIENT fait={(corr['r_trailing']>0).mean()*100:.1f}%")

    total_blocked = cap["r_trailing"].sum() + corr["r_trailing"].sum()
    print(f"\n  R cumule LAISSE SUR LA TABLE (signaux bloques, 1 seul compte) = {total_blocked:+.2f}R sur {len(cap)+len(corr)} signaux")
    print(f"  R cumule REELLEMENT PRIS (1 compte)                          = {taken['r_trailing'].sum():+.2f}R sur {len(taken)} signaux")
    print(f"\n  NOTE : dans la structure REELLE du projet (5 firms, plusieurs comptes en parallele), le cap "
          f"s'applique PAR COMPTE -- un signal bloque sur un compte peut etre pris par un autre (account_router "
          f"choisit le meilleur compte dispo). Ce replay 1-compte MAJORE donc le taux de blocage reel de la "
          f"flotte complete -- a lire comme une borne haute du cout d'opportunite par compte, pas la perte "
          f"nette de la flotte (qui a plusieurs comptes pour absorber la meme charge de signaux).")


if __name__ == "__main__":
    main()

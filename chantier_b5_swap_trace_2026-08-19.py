"""
Diagnostic complementaire B5 -- pourquoi 16 trades bloques ont statiquement
un RR superieur a leur occupant (categorie A theorique) mais seuls 3 sont
reellement swaps dans le mecanisme any-RR dynamique (chantier_b_ev2_
correlation_diag_2026-08-19.py:walkthrough_swap_rr) ? Trace, pour chacun
des 31 trades bloques identifies (walkthrough STATIQUE/baseline), ce qui
se passe reellement au meme instant dans le walkthrough DYNAMIQUE (swap
actif) : deja admis plus tot (occupant deja evince par un swap anterieur),
swap reussi ici, ou toujours bloque (occupant dynamique different/RR
different a cet instant precis).

N'importe pas ce script directement (convention du projet).
"""
import importlib.util

import pandas as pd

import robustness_5ers_risk_challenge as eng
from monte_carlo_simulation import precompute_correlation_pairs

ISO_SCRIPT = "chantier_strategie_b_isolation_indices_2026-08-18.py"
spec = importlib.util.spec_from_file_location("iso_trace", ISO_SCRIPT)
iso = importlib.util.module_from_spec(spec)
spec.loader.exec_module(iso)

CORR_TH = 0.80

if __name__ == "__main__":
    pop_B = iso.build_pop_B("tout_indices")
    pop_B = pop_B.sort_values("date_creation").reset_index(drop=True)
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop_B["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)

    # Identifiants des 31 trades bloques statiques (ticker, date_creation) charges du CSV resume
    static_blocked = pd.read_csv("chantier_b5_1_fiche_identite_resume_2026-08-19.csv")
    static_blocked["date_creation"] = pd.to_datetime(static_blocked["date_creation"])
    static_keys = set(zip(static_blocked["ticker"], static_blocked["date_creation"]))
    static_cat_a_keys = set(zip(
        static_blocked[static_blocked["rr_tp1"] > static_blocked["occ_rrs"].astype(str).str.split(",").str[0].astype(float)]["ticker"],
        static_blocked[static_blocked["rr_tp1"] > static_blocked["occ_rrs"].astype(str).str.split(",").str[0].astype(float)]["date_creation"]))

    open_positions = []
    trace_rows = []
    for i, row in pop_B.iterrows():
        now = row["date_creation"]
        close_time = row["resolution_time_est"]
        ticker = row["ticker"]
        r = row["r_trailing"] if row["statut_final"] == "OBJECTIF ATTEINT" else -1.0
        rr = row["rr_tp1"]
        key = (ticker, now)

        open_positions = [p for p in open_positions if p[1] > now]
        at_cap = len(open_positions) >= eng.MAX_POSITIONS
        conflicts = [p for p in open_positions if p[0] in excluded_map[ticker]]

        admitted = False
        outcome = None
        if key in static_cat_a_keys:
            if at_cap:
                outcome = "bloque_cap_position (dynamique different du statique)"
            elif not conflicts:
                outcome = "DEJA_ADMIS (occupant statique deja evince plus tot par un swap anterieur)"
                admitted = True
            elif len(conflicts) == 1 and rr > conflicts[0][3]:
                occ = conflicts[0]
                open_positions = [p for p in open_positions if p is not occ]
                outcome = f"SWAP_REUSSI (evince {occ[0]}, RR occupant dynamique={occ[3]:.2f})"
                admitted = True
            else:
                if len(conflicts) == 1:
                    outcome = f"TOUJOURS_BLOQUE (occupant dynamique={conflicts[0][0]} RR={conflicts[0][3]:.2f} >= RR bloque {rr:.2f})"
                else:
                    outcome = f"TOUJOURS_BLOQUE (conflits multiples dynamiques, n={len(conflicts)})"
            trace_rows.append(dict(ticker=ticker, date_creation=now, rr_tp1=rr, outcome=outcome))
        elif not at_cap and not conflicts:
            admitted = True
        elif not at_cap and len(conflicts) == 1 and rr > conflicts[0][3]:
            occ = conflicts[0]
            open_positions = [p for p in open_positions if p is not occ]
            admitted = True

        if admitted:
            open_positions.append((ticker, close_time, rr, r, i))

    trace_df = pd.DataFrame(trace_rows)
    print(f"[verif] trades categorie A statique retrouves dans le trace : {len(trace_df)} (attendu 16)")
    print(trace_df.to_string(index=False))
    print("\nRepartition des issues dynamiques :")
    print(trace_df["outcome"].apply(lambda s: s.split(" (")[0]).value_counts())

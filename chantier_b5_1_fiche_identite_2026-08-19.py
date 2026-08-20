"""
Chantier B5-1 (2026-08-19) -- fiche d'identite complete des 31 trades
bloques-correlation sur B (diagnostic deja confirme : EV bloques=+1,7099R
vs EV admis=+0,7238R, delta=+0,9861R, IC95%=[+0,81;+2,68]).

Reutilise le meme walkthrough (chantier_b_ev2_correlation_diag_2026-08-19.py,
1 compte, MAX_POSITIONS, CORR_TH=0,80, matrice 19x19) mais enrichit chaque
trade bloque avec le detail complet de l'/des occupant(s) responsable(s) du
blocage : ticker, RR, resultat, correlation exacte, asset_class.

N'importe pas ce script directement (convention du projet).
"""
import importlib.util

import numpy as np
import pandas as pd

import robustness_5ers_risk_challenge as eng
from monte_carlo_simulation import precompute_correlation_pairs

ISO_SCRIPT = "chantier_strategie_b_isolation_indices_2026-08-18.py"
spec = importlib.util.spec_from_file_location("iso_b51", ISO_SCRIPT)
iso = importlib.util.module_from_spec(spec)
spec.loader.exec_module(iso)

CORR_TH = 0.80
INDEX_KEYWORDS = ["DAX40", "S&P500", "NASDAQ100"]


def asset_class(ticker):
    return "indice" if any(k in ticker.upper() for k in INDEX_KEYWORDS) else "forex"


def outcome_r_row(row):
    return row["r_trailing"] if row["statut_final"] == "OBJECTIF ATTEINT" else -1.0


if __name__ == "__main__":
    pop_B = iso.build_pop_B("tout_indices")
    pop_B = pop_B.sort_values("date_creation").reset_index(drop=True)
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(pop_B["ticker"].unique())
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_TH)

    open_positions = []  # (ticker, close_time, rr, r, idx)
    fiche_rows = []
    blocked_count = 0

    for i, row in pop_B.iterrows():
        now = row["date_creation"]
        close_time = row["resolution_time_est"]
        ticker = row["ticker"]
        rr = row["rr_tp1"]
        r = outcome_r_row(row)

        open_positions = [p for p in open_positions if p[1] > now]

        at_cap = len(open_positions) >= eng.MAX_POSITIONS
        conflicts = [p for p in open_positions if p[0] in excluded_map[ticker]]

        if at_cap:
            blocked_reason = "cap_position"
        elif conflicts:
            blocked_reason = "correlation"
        else:
            blocked_reason = None

        if blocked_reason == "correlation":
            blocked_count += 1
            occ_details = []
            for occ_ticker, occ_close, occ_rr, occ_r, occ_idx in conflicts:
                corr_val = corr_matrix.loc[ticker, occ_ticker] if (ticker in corr_matrix.index and
                                                                     occ_ticker in corr_matrix.columns) else np.nan
                occ_details.append(dict(occ_ticker=occ_ticker, occ_rr=occ_rr, occ_r=occ_r,
                                          occ_asset_class=asset_class(occ_ticker), correlation=corr_val))
            fiche_rows.append(dict(
                num=blocked_count, ticker=ticker, asset_class=asset_class(ticker), rr_tp1=rr,
                date_creation=now, r_si_pris=r, n_conflits=len(conflicts),
                occupants=occ_details,
            ))

        if blocked_reason is None:
            open_positions.append((ticker, close_time, rr, r, i))

    print(f"[verif] total bloques-correlation trouves : {len(fiche_rows)} (attendu 31)")

    # --- Tableau plat (1 ligne par occupant, trades a conflits multiples getting plusieurs lignes) ---
    flat_rows = []
    for fr in fiche_rows:
        for occ in fr["occupants"]:
            flat_rows.append(dict(
                num=fr["num"], date_creation=fr["date_creation"], ticker=fr["ticker"],
                asset_class=fr["asset_class"], rr_tp1=fr["rr_tp1"], r_si_pris=fr["r_si_pris"],
                n_conflits=fr["n_conflits"],
                occ_ticker=occ["occ_ticker"], occ_asset_class=occ["occ_asset_class"],
                occ_rr=occ["occ_rr"], occ_r=occ["occ_r"], correlation=occ["correlation"],
            ))
    flat_df = pd.DataFrame(flat_rows)
    flat_df.to_csv("chantier_b5_1_fiche_identite_flat_2026-08-19.csv", index=False)

    print("\n" + "=" * 100)
    print(f"FICHE D'IDENTITE -- {len(fiche_rows)} trades bloques-correlation (une ligne par occupant)")
    print("=" * 100)
    pd.set_option("display.max_rows", 200)
    pd.set_option("display.width", 220)
    print(flat_df.to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    # --- Resume 1 ligne par trade bloque (n_conflits, occupants agreges) ---
    summary_rows = []
    for fr in fiche_rows:
        occ_tickers = ", ".join(o["occ_ticker"] for o in fr["occupants"])
        occ_rrs = ", ".join(f"{o['occ_rr']:.2f}" for o in fr["occupants"])
        occ_rs = ", ".join(f"{o['occ_r']:+.2f}" for o in fr["occupants"])
        any_occupant_lost = any(o["occ_r"] < 0 for o in fr["occupants"])
        all_occupants_won = all(o["occ_r"] > 0 for o in fr["occupants"])
        summary_rows.append(dict(
            num=fr["num"], date_creation=fr["date_creation"], ticker=fr["ticker"],
            asset_class=fr["asset_class"], rr_tp1=round(fr["rr_tp1"], 3), r_si_pris=round(fr["r_si_pris"], 3),
            n_conflits=fr["n_conflits"], occupants=occ_tickers, occ_rrs=occ_rrs, occ_rs=occ_rs,
            occupant_a_perdu=any_occupant_lost, tous_occupants_ont_gagne=all_occupants_won,
        ))
    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv("chantier_b5_1_fiche_identite_resume_2026-08-19.csv", index=False)
    print("\n" + "=" * 100)
    print("RESUME (1 ligne par trade bloque)")
    print("=" * 100)
    print(summary_df.to_string(index=False))

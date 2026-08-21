"""chantier_midterm2022_retest_2026-08-23.py

Re-verification (session du 23/08) du test "effet midterm" fait en session du
21/08, AVANT le fix r_trailing (commit df261dc, 21/08 soir). Ce script
original n'a jamais ete commite au repo (introuvable par grep/git log) -- ce
chantier le reconstruit a l'identique sur le seul indice verifiable qu'on a :
la fenetre forex de l'epoque (18/08/2022->08/11/2022) donnait n=21 sur la
population B_tradable_pgp forex (hors indices, hors metaux) -- CONFIRME ICI
en filtrant pop_b (chantier_gold_silver_pop_B_tradable_pgp_2026-08-20.csv,
donnees maintenant CORRIGEES post-fix) sur cette meme fenetre : n=21 forex,
n=6 indices, exactement les chiffres cites par l'utilisateur. Population et
fenetre donc reconstruites a l'identique avec un niveau de confiance eleve.

QUESTION 1 : le test original comparait (vraisemblablement) la fenetre au
baseline global forex -- reproduit ici via un test a 2 echantillons
(Welch t-test + Mann-Whitney, les deux reportes) fenetre vs RESTE de la
population forex (fenetre exclue du baseline, comparaison propre).

QUESTION 2 : comparaison fenetre vs RESTE DE BLOC2 uniquement (meme regime
macro 2022-08-20->2023-12-17, sans la fenetre midterm) -- separe l'effet
"regime bloc2 deja connu" de l'effet "midterm specifique". Fait pour forex
ET indices.

QUESTION 3 : gold/argent (hors palladium/platine, hors forex/indices) sur
la meme fenetre -- jamais teste empiriquement jusqu'ici sur nos propres
trades, seulement cite comme fait externe (or = meilleur actif du cycle
midterm US historiquement).

Limite structurelle rappelee partout : un seul cycle midterm dans les
donnees (2018 hors couverture historique) -- meme un resultat propre reste
un indice qualitatif sur n=1, pas une regle validee statistiquement au sens
frequentiste usuel (on ne peut pas construire une distribution d'echantillonnage
de "l'effet midterm" avec un seul cycle observe).
"""
import importlib.util

import numpy as np
import pandas as pd
from scipy import stats as sps

_spec = importlib.util.spec_from_file_location("chocs", "chantier_fenetres_macro_chocs_2026-08-23.py")
chocs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(chocs)

MIDTERM_START, MIDTERM_END = pd.Timestamp("2022-08-18"), pd.Timestamp("2022-11-08")
INDEX_KEYWORDS = ["DAX40", "S&P500", "NASDAQ100", "^GDAXI", "^GSPC", "^NDX"]
METAL_KEYWORDS = ["GOLD", "SILVER", "PALLADIUM", "PLATINUM"]
GOLD_SILVER_KEYWORDS = ["GOLD", "SILVER"]


def classify(pop):
    is_idx = pop["ticker"].str.contains("|".join(INDEX_KEYWORDS), case=False, na=False)
    is_metal = pop["ticker"].str.contains("|".join(METAL_KEYWORDS), case=False, na=False)
    is_gs = pop["ticker"].str.contains("|".join(GOLD_SILVER_KEYWORDS), case=False, na=False)
    is_forex = ~is_idx & ~is_metal
    return is_forex, is_idx, is_metal, is_gs


def stats_r(series, label):
    n = len(series)
    if n == 0:
        print(f"  {label:38s} n=   0 (vide)")
        return dict(n=0, ev=float("nan"), winrate=float("nan"))
    wins = int((series > 0).sum())
    ev = series.mean()
    se = series.std(ddof=1) / np.sqrt(n) if n > 1 else float("nan")
    winrate = 100 * wins / n
    print(f"  {label:38s} n={n:4d} EV={ev:+.4f}R se={se:.4f} winrate={winrate:6.2f}%")
    return dict(n=n, ev=ev, se=se, winrate=winrate, wins=wins, series=series)


def compare(a_series, b_series, label_a, label_b):
    if len(a_series) < 2 or len(b_series) < 2:
        print(f"    (n trop petit pour un test formel : {label_a} n={len(a_series)}, {label_b} n={len(b_series)})")
        return float("nan"), float("nan")
    t_stat, p_t = sps.ttest_ind(a_series, b_series, equal_var=False)
    try:
        u_stat, p_mw = sps.mannwhitneyu(a_series, b_series, alternative="two-sided")
    except ValueError:
        p_mw = float("nan")
    print(f"    {label_a} vs {label_b} : Welch t-test p={p_t:.4f}  |  Mann-Whitney p={p_mw:.4f}")
    return p_t, p_mw


def main():
    pop_b = chocs.load_pop_b()
    is_forex, is_idx, is_metal, is_gs = classify(pop_b)

    in_window = (pop_b["date_creation"] >= MIDTERM_START) & (pop_b["date_creation"] < MIDTERM_END)
    print(f"Fenetre midterm 2022 : [{MIDTERM_START.date()} -> {MIDTERM_END.date()}]")
    print(f"  composition : forex={int((in_window & is_forex).sum())}, indices={int((in_window & is_idx).sum())}, "
          f"metaux(tous)={int((in_window & is_metal).sum())}, dont or/argent={int((in_window & is_gs).sum())}")

    edges = chocs.common_bloc_edges(chocs.load_pop_a(), pop_b)
    bloc2_lo, bloc2_hi = edges[1], edges[2]
    in_bloc2 = (pop_b["date_creation"] >= bloc2_lo) & (pop_b["date_creation"] < bloc2_hi)
    print(f"bloc2 (regime commun A/B) : [{bloc2_lo.date()} -> {bloc2_hi.date()}]")

    # ================================================================
    print("\n" + "=" * 95)
    print("QUESTION 1 -- fenetre midterm forex vs RESTE de la population forex (donnees r_trailing corrigees)")
    print("=" * 95)
    forex = pop_b[is_forex].reset_index(drop=True)
    forex_in_window = pop_b.loc[in_window & is_forex, "r_trailing"]
    forex_rest = pop_b.loc[~in_window & is_forex, "r_trailing"]
    r1_w = stats_r(forex_in_window, "fenetre midterm (forex, corrige)")
    r1_b = stats_r(forex_rest, "reste population forex (baseline)")
    p_t1, p_mw1 = compare(forex_in_window, forex_rest, "fenetre", "baseline forex")
    delta1 = r1_w["ev"] - r1_b["ev"]
    print(f"\n  delta EV = {delta1:+.4f}R  (rappel original pre-fix : p=0,0105, mecanisme 'gains plafonnes')")
    print(f"  -> {'ECART SURVIT' if (p_t1 < 0.05 or p_mw1 < 0.05) else 'ECART A DISPARU (artefact confirme)'} "
          f"sur donnees corrigees (seuil 0,05, Welch p={p_t1:.4f}, MW p={p_mw1:.4f})")

    # ================================================================
    print("\n" + "=" * 95)
    print("QUESTION 2 -- fenetre midterm vs RESTE DE BLOC2 (meme regime macro, sans effet midterm)")
    print("=" * 95)
    rest_bloc2_mask = in_bloc2 & ~in_window
    print(f"  reste de bloc2 (bloc2 moins fenetre midterm) : "
          f"[{pop_b.loc[rest_bloc2_mask,'date_creation'].min()} -> {pop_b.loc[rest_bloc2_mask,'date_creation'].max()}]")

    print("\n  -- FOREX --")
    fx_w = pop_b.loc[in_window & is_forex, "r_trailing"]
    fx_rb2 = pop_b.loc[rest_bloc2_mask & is_forex, "r_trailing"]
    r2fx_w = stats_r(fx_w, "midterm forex")
    r2fx_b = stats_r(fx_rb2, "reste bloc2 forex")
    p_t2fx, p_mw2fx = compare(fx_w, fx_rb2, "midterm forex", "reste bloc2 forex")
    print(f"  delta EV (midterm - reste bloc2) = {r2fx_w['ev']-r2fx_b['ev']:+.4f}R")

    print("\n  -- INDICES (n attendu tres faible, chiffre quand meme) --")
    idx_w = pop_b.loc[in_window & is_idx, "r_trailing"]
    idx_rb2 = pop_b.loc[rest_bloc2_mask & is_idx, "r_trailing"]
    r2idx_w = stats_r(idx_w, "midterm indices")
    r2idx_b = stats_r(idx_rb2, "reste bloc2 indices")
    p_t2idx, p_mw2idx = compare(idx_w, idx_rb2, "midterm indices", "reste bloc2 indices")
    if r2idx_w["n"]:
        print(f"  delta EV (midterm - reste bloc2) = {r2idx_w['ev']-r2idx_b['ev']:+.4f}R")

    fx_signif = (not np.isnan(p_t2fx)) and (p_t2fx < 0.05 or p_mw2fx < 0.05)
    print(f"\n  -> FOREX : {'signal midterm REEL en plus du regime bloc2' if fx_signif else 'INDISCERNABLE de bloc2 -- effet midterm = redite du regime bloc2'} "
          f"(Welch p={p_t2fx:.4f}, MW p={p_mw2fx:.4f})")
    print(f"  -> INDICES : n trop faible ({r2idx_w['n']}) pour conclure quoi que ce soit formellement, chiffre pour memoire seulement")

    # ================================================================
    print("\n" + "=" * 95)
    print("QUESTION 3 -- or/argent sur la fenetre midterm 2022 (jamais teste empiriquement avant)")
    print("=" * 95)
    gs_w = pop_b.loc[in_window & is_gs, "r_trailing"]
    gs_all_rest = pop_b.loc[~in_window & is_gs, "r_trailing"]
    gs_rb2 = pop_b.loc[rest_bloc2_mask & is_gs, "r_trailing"]
    r3_w = stats_r(gs_w, "midterm or/argent")
    r3_base = stats_r(gs_all_rest, "reste population or/argent (baseline global)")
    r3_rb2 = stats_r(gs_rb2, "reste bloc2 or/argent")
    print()
    p_t3a, p_mw3a = compare(gs_w, gs_all_rest, "midterm or/argent", "baseline global or/argent")
    p_t3b, p_mw3b = compare(gs_w, gs_rb2, "midterm or/argent", "reste bloc2 or/argent")
    print(f"\n  delta vs baseline global = {r3_w['ev']-r3_base['ev']:+.4f}R  |  delta vs reste bloc2 = {r3_w['ev']-r3_rb2['ev']:+.4f}R")
    gs_signif_any = any(p < 0.05 for p in [p_t3a, p_mw3a, p_t3b, p_mw3b] if not np.isnan(p))
    print(f"  -> {'thèse or=meilleur actif midterm SOUTENUE empiriquement (au moins un test <0,05)' if gs_signif_any else 'thèse or=meilleur actif midterm NON confirmee empiriquement sur nos donnees'} "
          f"(n={r3_w['n']}, trop petit de toute facon pour un verdict ferme)")

    # ================================================================
    print("\n" + "=" * 95)
    print("SYNTHESE -- ce qu'il reste de la these 'effet midterm specifique'")
    print("=" * 95)
    print(f"  Q1 (vs baseline global forex, comparable au test original pre-fix) : delta={delta1:+.4f}R, "
          f"Welch p={p_t1:.4f}, MW p={p_mw1:.4f}")
    print(f"  Q2 (vs reste de bloc2, forex) : delta={r2fx_w['ev']-r2fx_b['ev']:+.4f}R, "
          f"Welch p={p_t2fx:.4f}, MW p={p_mw2fx:.4f}")
    print(f"  Q2 (vs reste de bloc2, indices, n={r2idx_w['n']}) : "
          f"delta={(r2idx_w['ev']-r2idx_b['ev']) if r2idx_w['n'] else float('nan'):+.4f}R (indicatif seulement)")
    print(f"  Q3 (or/argent, n={r3_w['n']}) : vs baseline global delta={r3_w['ev']-r3_base['ev']:+.4f}R (p={min(p_t3a,p_mw3a):.4f}), "
          f"vs reste bloc2 delta={r3_w['ev']-r3_rb2['ev']:+.4f}R (p={min(p_t3b,p_mw3b):.4f})")
    print("\n  LIMITE STRUCTURELLE (rappel explicite) : un seul cycle midterm US couvert par les donnees")
    print("  (2018 hors couverture historique du signal Lutessia) -- meme un resultat propre et significatif")
    print("  au sens frequentiste (n=21-60 TRADES) reste un indice qualitatif sur n=1 CYCLE, pas une regle")
    print("  validee : on ne peut pas construire de distribution d'echantillonnage inter-cycles avec un seul cycle.")

    detail = pop_b.copy()
    detail["in_window"] = in_window
    detail["in_bloc2"] = in_bloc2
    detail["classe"] = np.select([is_forex, is_idx, is_gs], ["forex", "indices", "or_argent"], default="metal_autre")
    detail[in_window | rest_bloc2_mask].to_csv("chantier_midterm2022_retest_detail_2026-08-23.csv", index=False)


if __name__ == "__main__":
    main()

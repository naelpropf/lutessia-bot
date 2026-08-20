"""
Chantier B4-B (2026-08-19) -- re-test de la regle d'exclusion JPY-JPY sur B.

Regle exacte (citation) : `scaling_simulation.py:78-79`
    def is_jpy(ticker):
        return "JPY" in ticker
utilisee dans `monte_carlo_simulation.py:74-86` (precompute_correlation_pairs,
fonction REELLEMENT utilisee par tout le moteur actuel y compris les scripts
B) :
    if (is_jpy(a) and is_jpy(b)) or abs(corr_matrix.loc[a, b]) > threshold:
        s.add(b)
-> deux tickers contenant TOUS DEUX la sous-chaine "JPY" sont TOUJOURS
exclus l'un de l'autre, independamment de leur correlation mesuree.

Traitement des indices (verifie par citation, pas suppose) : aucun label
indice (DAX40 FULL0926/DAX40 PERF INDEX/NASDAQ100 - MINI NASDAQ100 FULL0926/
NASDAQ100 INDEX/S&P500 - MINI S&P500 FULL0926) ne contient la sous-chaine
"JPY" -- `is_jpy()` retourne False pour tous, la regle JPY ne s'applique
JAMAIS aux indices ni aux paires indice-JPY. Leur exclusion mutuelle reste
geree UNIQUEMENT par le seuil de correlation 0,80 (matrice 19x19 deja
construite, ex. NASDAQ100<->S&P500=+0,954). Aucune adaptation necessaire --
confirme par lecture du code, pas par hypothese.

Historique : justification d'origine (8,81% DD flottant combine AUD/JPY-
USD/JPY) invalidee par un bug de fenetre calendaire (corrige), MAIS
RECONFIRMEE le 08/12 avec un chiffre frais (1,53% max sur la population
721 forex-only de l'epoque, registre_parametres_projet.md S2.60) -- la
regle n'est donc PAS juste "prudence structurelle non justifiee" comme le
prompt le suppose, elle a deja ete re-testee empiriquement une fois (mais
jamais sur B specifiquement, ni avec les indices).

Ce script reproduit le Volet A (diagnostic historique direct, PAS de Monte
Carlo -- hors scope de ce chantier) de chantier1_jpy_rule_test_2026-08-12.py
sur B forex seul, PUIS sur B complet (indices inclus, meme si aucun index
n'est JPY -- verifie qu'aucune excursion combinee anormale n'existe entre
paires JPY et indices via la correlation simple, en complement).

N'importe pas ce script directement (convention du projet).
"""
import importlib.util
import itertools

import pandas as pd

from daily_dd_pair_analysis import build_trade_day_excursions, analyze_pairs, RISK_PCT_PER_TRADE
from scaling_simulation import is_jpy

ISO_SCRIPT = "chantier_strategie_b_isolation_indices_2026-08-18.py"
spec = importlib.util.spec_from_file_location("iso_b4b", ISO_SCRIPT)
iso = importlib.util.module_from_spec(spec)
spec.loader.exec_module(iso)

INDEX_KEYWORDS = ["DAX40", "S&P500", "NASDAQ100"]


def prep_pop(pop):
    pop = pop.copy()
    pop["is_long"] = pop["stop_loss_init"] < pop["prix_entree"]
    pop["resolution_time"] = pop["resolution_time_est"]
    return pop


if __name__ == "__main__":
    pop_B = iso.build_pop_B("tout_indices")
    is_index = pop_B["ticker"].str.contains("|".join(INDEX_KEYWORDS), case=False, na=False)
    pop_B_fx = pop_B[~is_index].reset_index(drop=True)
    print(f"[verif] B forex n={len(pop_B_fx)}, B complet (avec indices) n={len(pop_B)}")

    print("\n" + "=" * 78)
    print("Traitement des indices par la regle JPY-JPY (verification code)")
    print("=" * 78)
    idx_tickers = sorted(pop_B[is_index]["ticker"].unique())
    for t in idx_tickers:
        print(f"  is_jpy({t!r}) = {is_jpy(t)}")

    print("\n" + "=" * 78)
    print("VOLET A -- diagnostic historique direct, B FOREX seul")
    print("=" * 78)
    pop_fx_prepped = prep_pop(pop_B_fx)
    jpy_tickers = sorted(t for t in pop_fx_prepped["ticker"].unique() if is_jpy(t))
    print(f"[verif] paires JPY presentes dans B forex : {jpy_tickers}")

    trade_days_fx = build_trade_day_excursions(pop_fx_prepped)
    jpy_result_fx = analyze_pairs(trade_days_fx, jpy_tickers)
    jpy_result_fx = jpy_result_fx.sort_values("max_dd_flottant_pct", ascending=False).reset_index(drop=True)
    print(jpy_result_fx.to_string(index=False))
    max_dd_fx = jpy_result_fx["max_dd_flottant_pct"].max()
    print(f"\n[VOLET A -- B forex] Max DD flottant combine sur les {len(jpy_result_fx)} duos JPY-JPY : "
          f"{max_dd_fx:.2f}% (reference A 08/12 sur 721 trades forex : 1,53%)")

    print("\n" + "=" * 78)
    print("VOLET A -- diagnostic historique direct, B COMPLET (forex+indices)")
    print("=" * 78)
    pop_full_prepped = prep_pop(pop_B)
    trade_days_full = build_trade_day_excursions(pop_full_prepped)
    jpy_result_full = analyze_pairs(trade_days_full, jpy_tickers)  # memes 5 paires JPY (indices jamais JPY)
    jpy_result_full = jpy_result_full.sort_values("max_dd_flottant_pct", ascending=False).reset_index(drop=True)
    max_dd_full = jpy_result_full["max_dd_flottant_pct"].max()
    print(f"[VOLET A -- B complet] Max DD flottant combine sur les {len(jpy_result_full)} duos JPY-JPY : "
          f"{max_dd_full:.2f}% (identique a B forex par construction -- ajouter des indices "
          f"non-JPY ne peut pas changer un calcul restreint aux 5 tickers JPY)")

    print("\n" + "=" * 78)
    print("COMPLEMENT -- correlation JPY<->indices (paires potentiellement sous-estimees "
          "par le seuil 0,80 seul, verification qu'aucune n'est proche du seuil)")
    print("=" * 78)
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    rows = []
    for jt, it in itertools.product(jpy_tickers, idx_tickers):
        if jt in corr_matrix.index and it in corr_matrix.columns:
            rows.append((jt, it, corr_matrix.loc[jt, it]))
    corr_df = pd.DataFrame(rows, columns=["jpy_ticker", "index_ticker", "correlation"])
    corr_df = corr_df.reindex(corr_df["correlation"].abs().sort_values(ascending=False).index)
    print(corr_df.head(10).to_string(index=False))
    print(f"\nMax |correlation| JPY<->indice : {corr_df['correlation'].abs().max():.3f} "
          f"(seuil d'exclusion = 0,80)")

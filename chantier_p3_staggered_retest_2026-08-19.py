"""
Point 3 (session 18/08->19/08) -- re-test du deblocage echelonne par firm
(seuils independants Blueberry->FTMO->Fivers->GFT->FundedNext, teste
08/08 dans extra_account_v4_multi_stagger.py : +7,2%/+7,8% profit,
annee1<0 -5pt vs le "deblocage groupe" pre-existant, seuil UNIQUE partage
DEFAULT_RESERVE=30000$ pour tous les firms simultanement) SOUS LA PILE
ACTUELLE COMPLETE.

DECOUVERTE PREALABLE (verifiee par citation de code) : le mecanisme
"echelonne par firm" n'est PAS un candidat externe a re-tester depuis
zero -- il est deja STRUCTURELLEMENT integre dans la reference officielle
actuelle. `ei.seq_grouped_multi(t_ftmo, t_fivers, t_gft, t_fundednext)`
(etape_e_fleet_integration.py:144-151, reprend exactement la meme
signature que extra_account_v4_multi_stagger.py:39) est la fonction
utilisee par TOUS les scripts backant §1.8 actuel (chantier_S1_8_officiel_
n600_risque_corrige_2026-08-17.py, chantier_strategie_b_isolation_indices_
2026-08-18.py, etc.), appelee avec seq_grouped_multi(1000, 15000, 25000,
25000) -- 4 seuils INDEPENDANTS, donc echelonnement actif par construction.

Ce qui n'a jamais ete mesure sous la pile actuelle complete (RR>=1,35,
any-RR, correctif risque Instant 1,5%, rr_tp2 §2.35) : la VALEUR AJOUTEE
de cet echelonnement, c-a-d REF (seuils actuels 1000/15000/25000/25000)
vs un comparateur "deblocage groupe" a seuil UNIQUE partage (reprend
exactement le DEFAULT_RESERVE=30000$ pre-08/08 documente dans
extra_account_v4_multi_stagger.py:27/36 et registre_parametres_projet.md
ligne 752, "Reserve >=30 000$ avant deblocage groupe", seul point de
comparaison historique disponible) -- teste ici via le MEME
seq_grouped_multi() avec les 4 seuils fixes a 30000$.

Reutilise integralement chantier_S1_8_officiel_n600_risque_corrige_2026-
08-17.py via importlib -- AUCUNE duplication de la logique de simulation,
seul l'argument `seq` de run_propagated change entre les 2 variantes.

N'importe pas ce script directement (convention du projet).
"""
import importlib.util
import sys
import time

import pandas as pd

REF_SCRIPT = "chantier_S1_8_officiel_n600_risque_corrige_2026-08-17.py"

spec = importlib.util.spec_from_file_location("ref_s18_p3", REF_SCRIPT)
ref = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ref)

INDEX_KEYWORDS = ["DAX40", "S&P500", "NASDAQ100", "DJ30"]


def load_common_forex_only():
    """Meme garde-fou que Point 2 : REF officiel actuel = population forex-
    only (631), pas encore regenere avec les indices (point ouvert #2 du
    handoff 08/18) -- market_data REF ne couvre pas les indices."""
    pop, market_data, excluded_map = ref.load_common()
    is_index = pop["ticker"].str.contains("|".join(INDEX_KEYWORDS), case=False, na=False)
    n_before = len(pop)
    pop = pop[~is_index].reset_index(drop=True)
    if len(pop) != n_before:
        tickers = sorted(pop["ticker"].unique())
        excluded_map = ref.precompute_correlation_pairs(
            tickers, pd.read_csv("correlation_matrix.csv", index_col=0), ref.CORR_TH_NEW)
    return pop, market_data, excluded_map


def run_variant(pop, market_data, excluded_map, n_sims, ceilings, seq, label):
    config = ref.ei.CONFIG_REF
    common_kwargs = dict(emergency=ref.ei.DEFAULT_EMERGENCY, eval_risk=ref.EVAL_RISK, fleet_risk=ref.FLEET_RISK,
                          gft_eval_risk=ref.GFT_EVAL_RISK, reserve_share=ref.ei.FINAL_RESERVE_SHARE,
                          extra_threshold_mult=ref.ei.EXTRA_THRESHOLD_MULT, n_sims=n_sims, seed=9999,
                          b_entry_frac=0.20, b_reduction=0.5, pre_unlock_only=True,
                          ftmo_discount=True, gft_goat_guard=True, payout_cycle=True,
                          use_any_rr=True, apply_instant_risk_cap=True)
    BB_THRESHOLD_BY_CEILING = {960.0: 5000.0, 1000.0: 5000.0, 3000.0: 0.0, 5000.0: 0.0}
    rows = []
    for ceiling in ceilings:
        bb_th = BB_THRESHOLD_BY_CEILING[ceiling]
        t0 = time.time()
        df = ref.run_propagated(pop, market_data, excluded_map, ceiling, seq, config,
                                 bb_threshold=bb_th, **common_kwargs)
        row = ref.summarize(df, label, ceiling, bb_th, True)
        rows.append(row)
        print(f"[{label:20s} plafond={ceiling:.0f}$] profit_moy={row['profit_moyen']:+,.0f}$ "
              f"solde_neg={row['solde_negatif_annee4']:.2f}% hit_ceiling={row['hit_ceiling_pct']:.2f}% "
              f"annee1<0={row['annee1_neg']:.2f}% ({time.time()-t0:.0f}s)")
    return pd.DataFrame(rows)


if __name__ == "__main__":
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    ceilings = [float(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [960.0, 1000.0, 3000.0, 5000.0]

    t_start = time.time()
    pop, market_data, excluded_map = load_common_forex_only()
    print(f"[verif] population REF (forex-only) : {len(pop)} trades")

    seq_staggered = ref.ei.seq_grouped_multi(1000, 15000, 25000, 25000)
    seq_groupe = ref.ei.seq_grouped_multi(30000, 30000, 30000, 30000)

    print("\n" + "=" * 70)
    print("REF actuel (echelonne 1000/15000/25000/25000$, deja adopte)")
    print("=" * 70)
    df_stag = run_variant(pop, market_data, excluded_map, n_sims, ceilings, seq_staggered, "REF_echelonne")

    print("\n" + "=" * 70)
    print("Comparateur : deblocage groupe seuil unique 30000$ (baseline pre-08/08)")
    print("=" * 70)
    df_grp = run_variant(pop, market_data, excluded_map, n_sims, ceilings, seq_groupe, "groupe_30000")

    print("\n" + "=" * 70)
    print("COMPARAISON echelonne (REF) vs groupe (baseline historique)")
    print("=" * 70)
    for ceiling in ceilings:
        r = df_stag[df_stag["ceiling"] == ceiling].iloc[0]
        g = df_grp[df_grp["ceiling"] == ceiling].iloc[0]
        d_profit_pct = (r["profit_moyen"] - g["profit_moyen"]) / abs(g["profit_moyen"]) * 100
        print(f"  plafond={ceiling:.0f}$ : profit groupe {g['profit_moyen']:+,.0f}$ -> echelonne {r['profit_moyen']:+,.0f}$ "
              f"({d_profit_pct:+.2f}%) | solde_neg {g['solde_negatif_annee4']:.2f}% -> {r['solde_negatif_annee4']:.2f}% "
              f"| hit_ceiling {g['hit_ceiling_pct']:.2f}% -> {r['hit_ceiling_pct']:.2f}% "
              f"| annee1<0 {g['annee1_neg']:.2f}% -> {r['annee1_neg']:.2f}% "
              f"(delta {r['annee1_neg']-g['annee1_neg']:+.2f}pt)")

    df_stag.to_csv(f"chantier_p3_staggered_echelonne_n{n_sims}_2026-08-19.csv", index=False)
    df_grp.to_csv(f"chantier_p3_staggered_groupe_n{n_sims}_2026-08-19.csv", index=False)
    print(f"\nTermine en {time.time()-t_start:.0f}s.")

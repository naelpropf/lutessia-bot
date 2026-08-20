"""ADX>32,27 restreint aux SEULS trades forex/indices de B_tradable
(2026-08-20) -- suite du retest du 19-20/08 (registre_strategie_
trading.md S6.3, script chantier_gold_silver_adx_sizing_retest_2026-08-
19.py).

Etape 0 (verification prealable, citation de code) : le retest du 19-20/
08 appliquait-il le filtre ADX/le sizing rr_tp1 a TOUTE la population B
(metaux inclus), ou seulement au sous-ensemble forex/indices ?

- ADX>32,27 : applique a TOUTE la population B, metaux inclus.
  chantier_gold_silver_adx_sizing_retest_2026-08-19.py:125-127 separe
  pop_B en fximd/metaux SEULEMENT pour calculer adx_at_entry sur les 2
  sous-ensembles (methodes de bougies differentes), MAIS :139
  (`pop_B_adx_full = pd.concat([pop_B_fximd, pop_B_metaux], ...)`) les
  refusionne AVANT le filtre, et :148 (`pop_B_adx_filtered = pop_B_
  adx_full[~(pop_B_adx_full["adx_at_entry"]>ADX_TH)]`) filtre la
  population FUSIONNEE -- les trades metaux avec adx_at_entry>32,268
  SONT exclus au meme titre que les forex/indices. Donc PAS deja
  restreint : ce chantier teste une idee neuve.

- rr_tp1<=1,25-sizing (x0,7) : DEJA restreint aux forex/indices, de
  facto, par construction du moteur -- chantier_gold_silver_adx_sizing_
  retest_2026-08-19.py:192-202, la boucle d'evenements route tout trade
  B-metal via `gse.route_metal_config2(...)` (ligne 193-194) AVANT
  toute logique de sizing ; le multiplicateur `size_func_B` n'est
  applique QUE dans la branche `else` (ligne 196-199), qui exclut par
  construction tous les trades metaux. `route_metal_config2`
  (chantier_gold_silver_ab_engine_2026-08-19.py:104-115) appelle
  `trade_risk(accB)` directement (ligne 108), sans jamais recevoir de
  multiplicateur de sizing. CONCLUSION : l'idee "restreindre le sizing
  rr_tp1 aux forex/indices seulement" est deja EXACTEMENT ce qui a ete
  teste le 19-20/08 -- le rejet (-3,6%, registre S6.3) s'applique tel
  quel, PAS RETESTE ici (redondant).

Note methodologique additionnelle : le retest du 19-20/08 utilisait le
moteur SIMPLIFIE 2-comptes (chantier_gold_silver_ab_engine_2026-08-19.py),
PAS le moteur cascade officiel 5-firms (chantier_ab_metaux_cascade_
officiel_2026-08-19.py) -- ni la population B_tradable (7 tickers,
n=1051, chantier_gold_silver_pop_B_config0_tradable_2026-08-19.csv)
demandee ici, qui utilisait la population Config0/Config2 complete
(14 tickers, n=1505). Ce chantier change donc SIMULTANEMENT 3 choses
par rapport au retest d'origine : (a) portee du filtre restreinte aux
forex/indices [le changement demande], (b) moteur cascade officiel
5-firms au lieu du moteur reduit, (c) population B_tradable (7 tickers)
au lieu de Config0/Config2 (14 tickers) -- les 6 sous-periodes ne
seront donc PAS des fenetres calendaires strictement identiques a
celles du 19-20/08 (population differente => bornes min/max
differentes), mais suivent le MEME schema (H1/H2 + 4 blocs calendaires
communs A/B, chantier_ab_metaux_cascade_officiel_2026-08-19.py:
date_subperiods). A traiter comme un nouveau test dans son propre
referentiel (baseline B_tradable vs ADX-fx-only B_tradable, memes
fenetres pour les deux), pas comme une replication a l'identique.

Lancement sequentiel B->A, seuil adopte 3000$ (registre S6.5).
"""
import importlib.util
import sys
import time

import numpy as np
import pandas as pd

_spec_abm = importlib.util.spec_from_file_location("abm", "chantier_ab_metaux_cascade_officiel_2026-08-19.py")
abm = importlib.util.module_from_spec(_spec_abm)
_spec_abm.loader.exec_module(abm)

_spec_gsr = importlib.util.spec_from_file_location("gsr", "chantier_gold_silver_adx_sizing_retest_2026-08-19.py")
gsr = importlib.util.module_from_spec(_spec_gsr)
_spec_gsr.loader.exec_module(gsr)

ADX_TH = gsr.ADX_TH  # 32.268, inchange
SEQUENTIAL_THRESHOLD = 3000.0  # seuil adopte, registre S6.5

POP_TRADABLE_CSV = "chantier_gold_silver_pop_B_config0_tradable_2026-08-19.csv"
POP_METAUX_ALL_CSV = "chantier_gold_silver_pop_metaux_all_2026-08-19.csv"


def load_pop_B_tradable():
    pop = pd.read_csv(POP_TRADABLE_CSV)
    pop["date_creation"] = pd.to_datetime(pop["date_creation"])
    pop["resolution_time_est"] = pd.to_datetime(pop["resolution_time_est"])
    return pop


def derive_beta_prior(pop):
    """Meme convention EXACTE que la derivation Beta(533,520) de B_tradable
    (chantier_ab_metaux_tradable_config2_2026-08-19.py:17-22, verifiee par
    calcul direct : wins=(r_trailing>0), losses=(r_trailing<=0), prior
    Beta(1,1) -> Beta(wins+1, losses+1)) -- chaque population EXACTE doit
    avoir sa propre derivation (lecon du bug ALPHA_POST_B, registre S9.6),
    la population ADX-filtree-fx-only est une population DIFFERENTE de
    B_tradable brute, donc re-derivee ici plutot que reutiliser 533/520."""
    wins = int((pop["r_trailing"] > 0).sum())
    losses = int((pop["r_trailing"] <= 0).sum())
    return wins + 1, losses + 1, wins, losses


def build_adx_filtered_fx_only(pop_B_tradable, metal_set):
    is_metal = pop_B_tradable["ticker"].isin(metal_set)
    pop_fx = pop_B_tradable[~is_metal].copy().reset_index(drop=True)
    pop_metal = pop_B_tradable[is_metal].copy().reset_index(drop=True)
    print(f"B_tradable : {len(pop_fx)} forex/indices | {len(pop_metal)} metaux (jamais filtres)")

    print("Calcul ADX(14) forex/indices (formule inchangee, meme cache Yahoo H1 que le retest 19-20/08)...")
    candles_fx = gsr.build_candles_with_adx_forex_indices(pop_fx)
    pop_fx = gsr.compute_adx_at_entry(pop_fx, candles_fx)

    n_couverts = pop_fx["adx_at_entry"].notna().sum()
    n_exclus = (pop_fx["adx_at_entry"] > ADX_TH).sum()
    print(f"[verif] ADX couvert (fx/indices) : {n_couverts}/{len(pop_fx)} ({n_couverts/len(pop_fx)*100:.1f}%)")
    print(f"[verif] Trades fx/indices exclus (adx_at_entry>{ADX_TH}) : {n_exclus}/{len(pop_fx)}")

    pop_fx_filtered = pop_fx[~(pop_fx["adx_at_entry"] > ADX_TH)].drop(columns=["adx_at_entry"]).reset_index(drop=True)
    combined = pd.concat([pop_fx_filtered, pop_metal], ignore_index=True).sort_values("date_creation").reset_index(drop=True)
    print(f"[verif] Population ADX-fx-only : {len(combined)}/{len(pop_B_tradable)} "
          f"({len(pop_B_tradable)-len(combined)} exclus, tous forex/indices)")
    return combined


def make_baseline_and_lever():
    pop_B_tradable = load_pop_B_tradable()
    oa_all = pd.read_csv(POP_METAUX_ALL_CSV)
    metal_set = set(oa_all["ticker"].unique())

    alpha_base, beta_base, wins_base, losses_base = derive_beta_prior(pop_B_tradable)
    print(f"[baseline] B_tradable n={len(pop_B_tradable)} wins={wins_base} losses={losses_base} "
          f"-> Beta({alpha_base},{beta_base}) winrate={wins_base/len(pop_B_tradable)*100:.2f}%")
    assert (alpha_base, beta_base) == (533, 520), "derivation baseline ne matche pas la reference documentee 533/520"

    pop_adx_fx = build_adx_filtered_fx_only(pop_B_tradable, metal_set)
    alpha_lev, beta_lev, wins_lev, losses_lev = derive_beta_prior(pop_adx_fx)
    print(f"[adx_fx_only] population n={len(pop_adx_fx)} wins={wins_lev} losses={losses_lev} "
          f"-> Beta({alpha_lev},{beta_lev}) winrate={wins_lev/len(pop_adx_fx)*100:.2f}%")

    pop_adx_fx.to_csv("chantier_pop_B_tradable_adx_fx_only_2026-08-20.csv", index=False)
    return (pop_B_tradable, alpha_base, beta_base), (pop_adx_fx, alpha_lev, beta_lev)


def run_variant(pop_B_variant, alpha_b, beta_b, n_sims, ceilings, seed=9999):
    abm.build_pop_B = lambda: pop_B_variant
    abm.ALPHA_POST_B_METAUX = alpha_b
    abm.BETA_POST_B_METAUX = beta_b

    pop_A, _, _ = abm.load_common_A()
    pop_B = abm.build_pop_B()
    oa_all = pd.read_csv(POP_METAUX_ALL_CSV)
    metal_set = set(oa_all["ticker"].unique())
    market_data, excluded_map = abm.build_market_data_and_excluded_map(pop_A, pop_B)

    rows = []
    for ceiling in ceilings:
        t0 = time.time()
        df = abm.run_n_sims(pop_A, pop_B, ceiling, n_sims, seed, True, market_data, excluded_map, metal_set,
                             sequential_b_threshold=SEQUENTIAL_THRESHOLD)
        row = abm.summarize_df(df, "full_pop", ceiling)
        row["scope"] = "full"
        rows.append(row)
        print(f"  [full plafond={ceiling:.0f}$] profit_moy={row['profit_moyen']:+,.0f}$ "
              f"solde_neg_an4={row['solde_negatif_annee4']:.2f}% annee1<0={row['annee1_neg']:.2f}% "
              f"({time.time()-t0:.0f}s)")

    for n_parts, tag in ((2, "H"), (4, "bloc")):
        parts = abm.date_subperiods(pop_A, pop_B, n_parts)
        for i, (sub_A, sub_B) in enumerate(parts):
            if len(sub_A) < 10 or len(sub_B) < 10:
                print(f"  [{tag}{i+1}] sous-population trop petite (A={len(sub_A)}, B={len(sub_B)}) -- ignore")
                continue
            for ceiling in ceilings:
                t0 = time.time()
                df = abm.run_n_sims(sub_A, sub_B, ceiling, n_sims, seed, True, market_data, excluded_map, metal_set,
                                     sequential_b_threshold=SEQUENTIAL_THRESHOLD)
                row = abm.summarize_df(df, f"{tag}{i+1}", ceiling)
                row["scope"] = f"{tag}{i+1}"
                row["n_trades_A"] = len(sub_A)
                row["n_trades_B"] = len(sub_B)
                rows.append(row)
                print(f"  [{tag}{i+1} plafond={ceiling:.0f}$] profit_moy={row['profit_moyen']:+,.0f}$ "
                      f"solde_neg_an4={row['solde_negatif_annee4']:.2f}% annee1<0={row['annee1_neg']:.2f}% "
                      f"({time.time()-t0:.0f}s)")
    return pd.DataFrame(rows)


def main():
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    ceilings = [float(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [3000.0, 5000.0]
    out_tag = sys.argv[3] if len(sys.argv) > 3 else f"n{n_sims}"

    (pop_base, a_base, b_base), (pop_lev, a_lev, b_lev) = make_baseline_and_lever()

    print(f"\n{'='*78}\nBASELINE B_tradable (n={n_sims}, seuil sequentiel {SEQUENTIAL_THRESHOLD:.0f}$)\n{'='*78}")
    df_base = run_variant(pop_base, a_base, b_base, n_sims, ceilings)
    df_base["variant"] = "baseline"

    print(f"\n{'='*78}\nADX>{ADX_TH} restreint forex/indices SEULEMENT (metaux jamais filtres)\n{'='*78}")
    df_lev = run_variant(pop_lev, a_lev, b_lev, n_sims, ceilings)
    df_lev["variant"] = "adx_fx_only"

    out = pd.concat([df_base, df_lev], ignore_index=True)
    out_path = f"chantier_adx_fx_only_B_tradable_{out_tag}_2026-08-20.csv"
    out.to_csv(out_path, index=False)
    print(f"\nSauvegarde : {out_path}")

    print(f"\n{'='*78}\nRESUME (delta = adx_fx_only - baseline)\n{'='*78}")
    for scope in df_base["scope"].unique():
        for ceiling in ceilings:
            b = df_base[(df_base["scope"] == scope) & (df_base["ceiling"] == ceiling)]
            l = df_lev[(df_lev["scope"] == scope) & (df_lev["ceiling"] == ceiling)]
            if b.empty or l.empty:
                continue
            db = b.iloc[0]["profit_moyen"]
            dl = l.iloc[0]["profit_moyen"]
            pct = (dl - db) / abs(db) * 100 if db != 0 else float("nan")
            print(f"  [{scope} c={ceiling:.0f}$] baseline={db:+,.0f}$ adx_fx_only={dl:+,.0f}$ delta={pct:+.1f}%")


if __name__ == "__main__":
    main()

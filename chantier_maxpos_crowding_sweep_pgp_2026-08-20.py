"""chantier_maxpos_crowding_sweep_pgp_2026-08-20.py

Objectif (demande utilisateur, session du 20/08 soir) : fusionner 2 chantiers
sur B_tradable+Pd/Pt (n=1248) avec la pile actuelle (ADX-fx-only + trailing
0,10x deja bake + sequentiel B->A 3000$, config "COMBO" de
chantier_adx_combo_stack_pgp_2026-08-20.py) :

1. Instrumenter cap_blocked_count (deja trackee en interne par
   process_one_account depuis le chantier etape0/1 du 19/08, ligne ~501,
   MAIS jamais exposee par summarize_df) -- comparer le taux de blocage par
   capacite (MAX_POSITIONS) du trader B entre H2/bloc4 (fenetres ou le profit
   se degrade sur n=1248 vs l'ancienne population) et bloc1/bloc2/bloc3 (ou
   l'interaction ADX x population elargie ne se manifeste pas).
2. Sweep MAX_POSITIONS in {3,4,5} sur cette meme pile/population -- est-ce
   que monter le plafond de positions simultanees resorbe la degradation
   H2/bloc4 en libérant directement la contrainte de capacite ? (MAX_POSITIONS
   jamais teste sur B_tradable seule -- seulement sur Config2-AB, point ouvert
   distinct du registre §7).

Genealogie / reutilise SANS reinvention :
- Population ADX-fx-only : PAS recalculee ici (couterait un nouveau calcul
  ADX(14) sur bougies H1, cf. chantier_adx_fx_only_B_tradable_2026-08-20.py:
  build_adx_filtered_fx_only) -- rechargee depuis le cache DEJA produit et
  documente reutilisable (chantier_pop_B_tradable_pgp_adx_fx_only_2026-08-20.
  csv, n=1193, Beta(607,588), cf. session_handoff_2026-08-20_soir.md §5).
  Prior re-derive par adxfx.derive_beta_prior (calcul de colonnes, pas de
  bougies) et verifie contre la reference documentee.
- Structure scope/ceiling (full + H1/H2 + bloc1-4) : logique copiee de
  chantier_adx_combo_stack_2026-08-20.py:45-86 (run_config), avec 2 ajouts :
  (a) metal_set corrige (cf. bug ci-dessous), (b) capture des colonnes
  B_cap_blocked/B_trades_admitted/B_corr_blocked du df brut (deja calculees
  par process_one_account, jamais exposees par summarize_df) + injection de
  eng.MAX_POSITIONS avant chaque appel (mecanisme documente et verifie par
  lecture de code, chantier_ab_metaux_cascade_officiel_2026-08-19.py:58-62 :
  `eng.MAX_POSITIONS = N` avant l'appel, lu a CHAQUE evenement par
  engine_multiformat.py:324, aucune valeur figee a l'import).

Bug supplementaire trouve en construisant ce chantier (meme classe que les 2
deja corriges le 20/08 -- correlation_matrix.csv commit dbe7e99, market_data
commit 0d85961) : `metal_set` utilise DANS run_config (chantier_adx_combo_
stack_2026-08-20.py:52-53, herite tel quel par le wrapper pgp existant
chantier_adx_combo_stack_pgp_2026-08-20.py, donc DEJA present dans le §7
refresh commite) est calcule depuis POP_METAUX_ALL_CSV =
chantier_gold_silver_pop_metaux_all_2026-08-19.csv (14 tickers GOLD/SILVER,
fige au 19/08, AVANT Pd/Pt -- verifie par lecture directe : PALLADIUM/PLATINUM
absents). Consequence : un trade B palladium/platine bloque par CORRELATION
(pas par cap) ne beneficie PAS de l'overflow-vers-A Config2 (reserve aux
trades du metal_set, chantier_ab_metaux_cascade_officiel_2026-08-19.py:691-
708), contrairement a un trade or/argent bloque de la meme facon -- perte
seche au lieu d'une tentative sur A. N'AFFECTE PAS cap_blocked_count
directement : l'overflow n'est de toute facon jamais tente pour un trade
cap-bloque, meme dans le metal_set (`if admitted or at_cap: continue` avant
le bloc overflow, ligne 702) -- affecte seulement le sous-ensemble
corr_blocked des metaux Pd/Pt. Corrige ici par wrapper (convention du projet,
aucune modification des fichiers officiels) : metal_set etendu a
PALLADIUM/PLATINUM avant chaque appel.
"""
import importlib.util
import sys
import time

import numpy as np
import pandas as pd

_spec_stack_pgp = importlib.util.spec_from_file_location("stack_pgp", "chantier_adx_combo_stack_pgp_2026-08-20.py")
stack_pgp = importlib.util.module_from_spec(_spec_stack_pgp)
_spec_stack_pgp.loader.exec_module(stack_pgp)

abm = stack_pgp.abm
adxfx = stack_pgp.adxfx
SEQUENTIAL_THRESHOLD = stack_pgp.SEQUENTIAL_THRESHOLD  # 3000.0, inchange

ADX_FX_ONLY_CACHE = "chantier_pop_B_tradable_pgp_adx_fx_only_2026-08-20.csv"
EXPECTED_N_ADX = 1193
EXPECTED_ALPHA_ADX, EXPECTED_BETA_ADX = 607, 588
DEFAULT_MAX_POSITIONS = 3  # scaling_simulation.py:47, valeur projet par defaut


def load_combo_population():
    """COMBO = pile actuelle (ADX-fx-only + trailing deja bake + sequentiel
    3000$). Recharge la population ADX-fx-only DEJA calculee (voir docstring
    module), ne relance PAS le calcul ADX (bougies H1, couteux)."""
    pop_adx = pd.read_csv(ADX_FX_ONLY_CACHE)
    pop_adx["date_creation"] = pd.to_datetime(pop_adx["date_creation"])
    pop_adx["resolution_time_est"] = pd.to_datetime(pop_adx["resolution_time_est"])
    assert len(pop_adx) == EXPECTED_N_ADX, f"n inattendu : {len(pop_adx)} (attendu {EXPECTED_N_ADX})"
    alpha_adx, beta_adx, wins, losses = adxfx.derive_beta_prior(pop_adx)
    assert (alpha_adx, beta_adx) == (EXPECTED_ALPHA_ADX, EXPECTED_BETA_ADX), \
        f"derivation ADX-fx-only ne matche pas la reference documentee : Beta({alpha_adx},{beta_adx})"
    print(f"[COMBO pop] n={len(pop_adx)} wins={wins} losses={losses} -> Beta({alpha_adx},{beta_adx})", flush=True)
    return pop_adx, alpha_adx, beta_adx


def build_metal_set_fixed():
    """Cf. section "Bug supplementaire" du docstring module."""
    oa_all = pd.read_csv(adxfx.POP_METAUX_ALL_CSV)
    metal_set = set(oa_all["ticker"].unique())
    n_before = len(metal_set)
    metal_set |= {"PALLADIUM", "PLATINUM"}
    print(f"[metal_set corrige] {n_before} -> {len(metal_set)} tickers (PALLADIUM/PLATINUM ajoutes)", flush=True)
    return metal_set


def cap_blocked_stats(df, tid="B"):
    admitted = df[f"{tid}_trades_admitted"]
    cap_blocked = df[f"{tid}_cap_blocked"]
    corr_blocked = df[f"{tid}_corr_blocked"]
    total_attempts = (admitted + cap_blocked + corr_blocked).replace(0, np.nan)
    cap_rate = cap_blocked / total_attempts
    return {
        f"{tid}_admitted_moy": admitted.mean(),
        f"{tid}_cap_blocked_moy": cap_blocked.mean(),
        f"{tid}_corr_blocked_moy": corr_blocked.mean(),
        f"{tid}_cap_blocked_rate_pct": cap_rate.mean() * 100,
    }


def run_config_instrumented(pop_B, alpha_b, beta_b, sequential_threshold, n_sims, ceilings, metal_set,
                             max_positions, seed=9999):
    abm.eng.MAX_POSITIONS = max_positions
    abm.build_pop_B = lambda: pop_B
    abm.ALPHA_POST_B_METAUX = alpha_b
    abm.BETA_POST_B_METAUX = beta_b

    pop_A, _, _ = abm.load_common_A()
    pop_B_loaded = abm.build_pop_B()
    market_data, excluded_map = abm.build_market_data_and_excluded_map(pop_A, pop_B_loaded)

    rows = []
    for ceiling in ceilings:
        t0 = time.time()
        df = abm.run_n_sims(pop_A, pop_B_loaded, ceiling, n_sims, seed, True, market_data, excluded_map, metal_set,
                             sequential_b_threshold=sequential_threshold)
        row = abm.summarize_df(df, "full_pop", ceiling)
        row.update(cap_blocked_stats(df, "B"))
        row["scope"] = "full"
        row["max_positions"] = max_positions
        rows.append(row)
        print(f"  [full MP={max_positions} plafond={ceiling:.0f}$] profit_moy={row['profit_moyen']:+,.0f}$ "
              f"cap_blocked_moy={row['B_cap_blocked_moy']:.1f} cap_rate={row['B_cap_blocked_rate_pct']:.2f}% "
              f"annee1<0={row['annee1_neg']:.2f}% ({time.time()-t0:.0f}s)", flush=True)

    for n_parts, tag in ((2, "H"), (4, "bloc")):
        parts = abm.date_subperiods(pop_A, pop_B_loaded, n_parts)
        for i, (sub_A, sub_B) in enumerate(parts):
            if len(sub_A) < 10 or len(sub_B) < 10:
                print(f"  [{tag}{i+1}] sous-population trop petite (A={len(sub_A)}, B={len(sub_B)}) -- ignore",
                      flush=True)
                continue
            for ceiling in ceilings:
                t0 = time.time()
                df = abm.run_n_sims(sub_A, sub_B, ceiling, n_sims, seed, True, market_data, excluded_map, metal_set,
                                     sequential_b_threshold=sequential_threshold)
                row = abm.summarize_df(df, f"{tag}{i+1}", ceiling)
                row.update(cap_blocked_stats(df, "B"))
                row["scope"] = f"{tag}{i+1}"
                row["max_positions"] = max_positions
                row["n_trades_A"] = len(sub_A)
                row["n_trades_B"] = len(sub_B)
                rows.append(row)
                print(f"  [{tag}{i+1} MP={max_positions} plafond={ceiling:.0f}$] profit_moy={row['profit_moyen']:+,.0f}$ "
                      f"cap_blocked_moy={row['B_cap_blocked_moy']:.1f} cap_rate={row['B_cap_blocked_rate_pct']:.2f}% "
                      f"annee1<0={row['annee1_neg']:.2f}% ({time.time()-t0:.0f}s)", flush=True)
    return pd.DataFrame(rows)


def main():
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 600
    ceilings = [float(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [3000.0, 5000.0]
    max_positions_values = [int(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else [3, 4, 5]
    out_tag = sys.argv[4] if len(sys.argv) > 4 else f"n{n_sims}"

    pop_adx, alpha_adx, beta_adx = load_combo_population()
    metal_set = build_metal_set_fixed()

    all_rows = []
    for mp in max_positions_values:
        print(f"\n{'='*78}\nMAX_POSITIONS={mp} (n={n_sims})\n{'='*78}", flush=True)
        df = run_config_instrumented(pop_adx, alpha_adx, beta_adx, SEQUENTIAL_THRESHOLD, n_sims, ceilings,
                                      metal_set, mp)
        df["config"] = "COMBO"
        all_rows.append(df)
        print(f"[MAX_POSITIONS={mp}] termine.", flush=True)

    out = pd.concat(all_rows, ignore_index=True)
    out_path = f"chantier_maxpos_crowding_sweep_pgp_{out_tag}_2026-08-20.csv"
    out.to_csv(out_path, index=False)
    print(f"\nSauvegarde : {out_path}", flush=True)

    print(f"\n{'='*78}\nCROWDING (cap_blocked_rate_pct, trader B, MAX_POSITIONS={DEFAULT_MAX_POSITIONS})\n{'='*78}",
          flush=True)
    base = out[out["max_positions"] == DEFAULT_MAX_POSITIONS]
    for ceiling in ceilings:
        sub = base[base["ceiling"] == ceiling].set_index("scope")
        print(f"-- plafond={ceiling:.0f}$ --", flush=True)
        for scope in ["full", "H1", "H2", "bloc1", "bloc2", "bloc3", "bloc4"]:
            if scope not in sub.index:
                continue
            r = sub.loc[scope]
            print(f"  [{scope}] cap_blocked_moy={r['B_cap_blocked_moy']:.1f} "
                  f"cap_rate={r['B_cap_blocked_rate_pct']:.2f}% profit_moy={r['profit_moyen']:+,.0f}$", flush=True)


if __name__ == "__main__":
    main()

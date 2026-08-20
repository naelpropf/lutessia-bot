"""Test de combinaison ADX-fx-only + sequentiel B->A 3000$ (2026-08-20),
suite de chantier_adx_fx_only_B_tradable_2026-08-20.py (confirme n=600,
mais toujours en layer sur-dessus du sequentiel 3000$ par defaut -- ce
script decompose explicitement l'effet sequentiel seul, ADX seul, et la
combinaison, pour verifier l'additivite (§7 registre, "cascade combinant
tous les leviers jamais testee ensemble").

Trailing 0,10x B N'EST PAS un axe de ce factoriel -- deja bake dans la
population B_tradable elle-meme (chantier_gold_silver_pop_B_config0_
tradable_2026-08-19.csv, colonne r_trailing), constant sur les 4
configurations, pas retoggle ici (deja adopte, hors perimetre de ce
test -- cf. instruction utilisateur "pas de nouveau levier").

Factoriel 2x2 sur B_tradable (1051 trades, 7 tickers metaux GOLD/SILVER
only -- PAS la population elargie avec palladium/platine, changement de
population explicitement exclu de ce test) :

  Config          | Lancement A          | Filtre B forex/indices
  ----------------|----------------------|------------------------
  1 REF           | jour0 (simultane)    | aucun (baseline B_tradable brut)
  2 SEQ_SEUL      | sequentiel 3000$     | aucun
  3 ADX_SEUL      | jour0 (simultane)    | ADX>32,27 exclu (fx only)
  4 COMBO         | sequentiel 3000$     | ADX>32,27 exclu (fx only)

Additivite attendue : delta(COMBO) ~= delta(SEQ_SEUL) + delta(ADX_SEUL)
(deltas mesures vs REF). Ecart notable = interaction a expliquer, avec
un regard particulier sur bloc2 (fenetre ou une interaction inattendue
avait deja ete trouvee par le passe, B_no_metals vs A-seule)."""
import importlib.util
import sys
import time

import numpy as np
import pandas as pd

_spec_adx = importlib.util.spec_from_file_location("adxfx", "chantier_adx_fx_only_B_tradable_2026-08-20.py")
adxfx = importlib.util.module_from_spec(_spec_adx)
_spec_adx.loader.exec_module(adxfx)

abm = adxfx.abm
POP_METAUX_ALL_CSV = adxfx.POP_METAUX_ALL_CSV
SEQUENTIAL_THRESHOLD = adxfx.SEQUENTIAL_THRESHOLD  # 3000.0


def run_config(pop_B_variant, alpha_b, beta_b, sequential_threshold, n_sims, ceilings, seed=9999):
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
                             sequential_b_threshold=sequential_threshold)
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
                                     sequential_b_threshold=sequential_threshold)
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

    (pop_ref, a_ref, b_ref), (pop_adx, a_adx, b_adx) = adxfx.make_baseline_and_lever()

    configs = [
        ("REF", pop_ref, a_ref, b_ref, None),
        ("SEQ_SEUL", pop_ref, a_ref, b_ref, SEQUENTIAL_THRESHOLD),
        ("ADX_SEUL", pop_adx, a_adx, b_adx, None),
        ("COMBO", pop_adx, a_adx, b_adx, SEQUENTIAL_THRESHOLD),
    ]

    all_rows = []
    for name, pop_v, a_v, b_v, seq_th in configs:
        print(f"\n{'='*78}\n{name} (sequential_threshold={seq_th}, n={n_sims})\n{'='*78}")
        df = run_config(pop_v, a_v, b_v, seq_th, n_sims, ceilings)
        df["config"] = name
        all_rows.append(df)

    out = pd.concat(all_rows, ignore_index=True)
    out_path = f"chantier_adx_combo_stack_{out_tag}_2026-08-20.csv"
    out.to_csv(out_path, index=False)
    print(f"\nSauvegarde : {out_path}")

    print(f"\n{'='*78}\nDECOMPOSITION ADDITIVE (delta vs REF, profit_moyen)\n{'='*78}")
    piv = {name: out[out["config"] == name].set_index(["scope", "ceiling"])["profit_moyen"] for name, *_ in configs}
    for scope in out["scope"].unique():
        for ceiling in ceilings:
            key = (scope, ceiling)
            if key not in piv["REF"].index:
                continue
            ref = piv["REF"][key]
            seq = piv["SEQ_SEUL"][key]
            adx = piv["ADX_SEUL"][key]
            combo = piv["COMBO"][key]
            d_seq = seq - ref
            d_adx = adx - ref
            d_combo = combo - ref
            d_additive = d_seq + d_adx
            interaction = d_combo - d_additive
            pct_interaction = interaction / abs(d_additive) * 100 if d_additive != 0 else float("nan")
            flag = " <<< bloc2" if scope == "bloc2" else ""
            print(f"[{scope} c={ceiling:.0f}$] REF={ref:+,.0f}$ | d_SEQ={d_seq:+,.0f}$ d_ADX={d_adx:+,.0f}$ "
                  f"| additif_attendu={d_additive:+,.0f}$ | COMBO_reel={d_combo:+,.0f}$ "
                  f"| interaction={interaction:+,.0f}$ ({pct_interaction:+.1f}% de l'additif){flag}")


if __name__ == "__main__":
    main()

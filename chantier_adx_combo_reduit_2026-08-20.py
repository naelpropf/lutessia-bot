"""Version reduite de chantier_adx_combo_stack_2026-08-20.py (2026-08-20,
suite immediate) : 2 configs seulement (REF, COMBO -- SEQ_SEUL/ADX_SEUL
retires, effets individuels deja connus par ailleurs), UN SEUL plafond
par invocation (pour lancer 3000$ et 5000$ en 2 process paralleles
separes plutot qu'une boucle sequentielle sur les 2).

Reutilise integralement chantier_adx_combo_stack_2026-08-20.py (run_config,
abm, make_baseline_and_lever) -- aucune nouvelle logique de simulation,
juste un scope reduit + prints flush=True (le run precedent avait un
fichier log qui restait a 0 octet en cours de route, bufferise sans
flush -- corrige ici pour pouvoir suivre la progression en direct)."""
import importlib.util
import sys
import time

import pandas as pd

_spec = importlib.util.spec_from_file_location("combo", "chantier_adx_combo_stack_2026-08-20.py")
combo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(combo)

adxfx = combo.adxfx
SEQUENTIAL_THRESHOLD = combo.SEQUENTIAL_THRESHOLD


def main():
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 600
    ceiling = float(sys.argv[2])  # UN seul plafond, obligatoire (3000 ou 5000)
    out_tag = sys.argv[3] if len(sys.argv) > 3 else f"n{n_sims}_c{ceiling:.0f}"

    print(f"Reconstruction population baseline + ADX-fx-only (cache CSV si deja fait)...", flush=True)
    (pop_ref, a_ref, b_ref), (pop_adx, a_adx, b_adx) = adxfx.make_baseline_and_lever()

    configs = [
        ("REF", pop_ref, a_ref, b_ref, None),
        ("COMBO", pop_adx, a_adx, b_adx, SEQUENTIAL_THRESHOLD),
    ]

    all_rows = []
    for name, pop_v, a_v, b_v, seq_th in configs:
        print(f"\n{'='*78}\n{name} (sequential_threshold={seq_th}, n={n_sims}, plafond={ceiling:.0f}$)\n{'='*78}", flush=True)
        df = combo.run_config(pop_v, a_v, b_v, seq_th, n_sims, [ceiling])
        df["config"] = name
        all_rows.append(df)
        print(f"[{name}] termine.", flush=True)

    out = pd.concat(all_rows, ignore_index=True)
    out_path = f"chantier_adx_combo_reduit_{out_tag}_2026-08-20.csv"
    out.to_csv(out_path, index=False)
    print(f"\nSauvegarde : {out_path}", flush=True)

    print(f"\n{'='*78}\nCOMBO vs REF (plafond={ceiling:.0f}$)\n{'='*78}", flush=True)
    piv = {name: out[out["config"] == name].set_index("scope") for name, *_ in configs}
    for scope in out["scope"].unique():
        ref_row = piv["REF"].loc[scope]
        combo_row = piv["COMBO"].loc[scope]
        d_profit = combo_row["profit_moyen"] - ref_row["profit_moyen"]
        pct = d_profit / abs(ref_row["profit_moyen"]) * 100 if ref_row["profit_moyen"] != 0 else float("nan")
        flag = " <<< bloc2" if scope == "bloc2" else ""
        print(f"[{scope}] REF profit={ref_row['profit_moyen']:+,.0f}$ annee1<0={ref_row['annee1_neg']:.2f}% "
              f"| COMBO profit={combo_row['profit_moyen']:+,.0f}$ annee1<0={combo_row['annee1_neg']:.2f}% "
              f"| delta_profit={d_profit:+,.0f}$ ({pct:+.1f}%){flag}", flush=True)


if __name__ == "__main__":
    main()

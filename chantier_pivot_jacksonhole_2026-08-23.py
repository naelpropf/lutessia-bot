"""chantier_pivot_jacksonhole_2026-08-23.py

Suite a chantier_pivot_bloc2_context_2026-08-23.py : teste specifiquement
la fenetre Jackson Hole 2022 (discours choc de Powell "some pain", 26/08/
2022 -- le seul precedent historique direct pour un evenement Jackson Hole
dans les donnees du projet, meme methode que SVB/israel_hamas/carry-unwind :
fenetre resserree 24 aout -> 2 septembre, 7 trades reels dans B_tradable_pgp
sur cette fenetre). Sert de proxy pour evaluer si trader a travers un
28/08/2026 potentiellement volatil degrade le classement pivot -- PAS un
proxy de la date elle-meme (2026 vs 2022), mais du TYPE d'evenement
(discours Fed choc).

Meme mecanisme forced_window_B que chantier_pivot_bloc2_context_2026-08-
23.py, meme patch run_dual_ab (A_activation_month/B_full_structure_month),
5 tailles de pivot, ceiling=1000$.
"""
import importlib.util
import inspect

import pandas as pd

_spec = importlib.util.spec_from_file_location("taskd", "chantier_taskD_sequential_BA_2026-08-23.py")
taskd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(taskd)

SEQUENTIAL_B_THRESHOLD = 3000.0
CEILING = 1000.0
N_SIMS = 300
JACKSON_HOLE = (pd.Timestamp("2022-08-24"), pd.Timestamp("2022-09-02"))

PIVOT_CONFIGS = [
    ("REF_25k_dynamique", dict(pivot_fmt_key=None, pivot_palier=None)),
    ("Pivot_InstantElite_2500", dict(pivot_fmt_key="Blueberry_InstantElite", pivot_palier=2500.0)),
    ("Pivot_InstantElite_5000", dict(pivot_fmt_key="Blueberry_InstantElite", pivot_palier=5000.0)),
    ("Pivot_InstantElite_10000", dict(pivot_fmt_key="Blueberry_InstantElite", pivot_palier=10000.0)),
    ("Pivot_InstantElite_25000", dict(pivot_fmt_key="Blueberry_InstantElite", pivot_palier=25000.0)),
]

src = inspect.getsource(taskd.run_dual_ab)
marker1 = 'st["A"]["_seq_activated"] = True'
lines0 = src.split("\n")
for i, line in enumerate(lines0):
    if marker1 in line:
        indent = line[:len(line) - len(line.lstrip())]
        lines0[i] = line + f'\n{indent}st["A"]["_seq_activated_month"] = now / MONTH_SECONDS'
        break
else:
    raise RuntimeError("point d'injection _seq_activated introuvable")
src = "\n".join(lines0)

marker2 = 'result["combined_hit_ceiling"] = combined_cash["hit_ceiling"]'
lines = src.split("\n")
for i, line in enumerate(lines):
    if marker2 in line:
        indent = line[:len(line) - len(line.lstrip())]
        lines[i] = (f'{indent}result["A_activation_month"] = st["A"].get("_seq_activated_month")\n'
                     f'{indent}result["B_full_structure_month"] = st["B"].get("full_structure_month")\n'
                     f'{line}')
        break
else:
    raise RuntimeError("point d'injection result dict introuvable")
src = "\n".join(lines)

code = compile(src, "<run_dual_ab_jh>", "exec")
exec(code, taskd.__dict__)


def run_config(pop_A, pop_B, n_sims, seed, market_data, excluded_map, metal_set, label, forced_window, kw):
    size_func = taskd.rr2.make_size_func_tail(1.6)
    df = taskd.run_n_sims(pop_A, pop_B, CEILING, n_sims, seed, True, market_data, excluded_map, metal_set,
                           sequential_b_threshold=SEQUENTIAL_B_THRESHOLD, size_func=size_func,
                           forced_window_B=forced_window, **kw)
    profit = df["combined_net"] - df["combined_is_paid"]
    a1_neg = (df["combined_year1_net"] < 0).mean() * 100
    solde_neg = (profit < 0).mean() * 100
    act = df["A_activation_month"].dropna()
    struct = df["B_full_structure_month"].dropna()
    n_active = df["A_activation_month"].notna().sum()
    print(f"[{label}] profit_moy={profit.mean():+,.0f}$ solde_neg={solde_neg:.2f}% annee1<0={a1_neg:.2f}% "
          f"A_active={n_active}/{n_sims} A_activation_month_median={act.median():.2f} "
          f"B_full_structure_month_median={struct.median() if len(struct) else float('nan'):.2f}", flush=True)
    return dict(label=label, profit_moy=profit.mean(), solde_neg=solde_neg, annee1_neg=a1_neg,
                A_activation_month_median=act.median() if len(act) else float("nan"),
                B_full_structure_month_median=struct.median() if len(struct) else float("nan"),
                A_never_activated_pct=100 * (1 - n_active / n_sims))


def main():
    pop_A, _, _ = taskd.load_common_A()
    pop_B = taskd.build_pop_B()
    oa_all = pd.read_csv("chantier_gold_silver_pop_metaux_all_2026-08-19.csv")
    metal_set = set(oa_all["ticker"].unique())
    market_data, excluded_map = taskd.build_market_data_and_excluded_map(pop_A, pop_B)
    n_w = int(((pop_B["date_creation"] >= JACKSON_HOLE[0]) & (pop_B["date_creation"] < JACKSON_HOLE[1])).sum())
    print(f"[verif] pop_A={len(pop_A)} pop_B={len(pop_B)} jackson_hole=[{JACKSON_HOLE[0].date()}->"
          f"{JACKSON_HOLE[1].date()}] n_trades={n_w} ceiling={CEILING:.0f}$", flush=True)

    rows = []
    for label, kw in PIVOT_CONFIGS:
        print(f"\n{'='*90}\n{label} -- BASELINE (bootstrap normal)\n{'='*90}", flush=True)
        row_base = run_config(pop_A, pop_B, N_SIMS, 9999, market_data, excluded_map, metal_set,
                               f"{label}_baseline", None, kw)
        row_base["variant"] = "baseline"
        rows.append(row_base)

        print(f"\n{'='*90}\n{label} -- JACKSON HOLE force en 1er\n{'='*90}", flush=True)
        row_jh = run_config(pop_A, pop_B, N_SIMS, 9999, market_data, excluded_map, metal_set,
                             f"{label}_jh", JACKSON_HOLE, kw)
        row_jh["variant"] = "jackson_hole_force"
        rows.append(row_jh)

        delta_speed = row_jh["A_activation_month_median"] - row_base["A_activation_month_median"]
        delta_risk = row_jh["solde_neg"] - row_base["solde_neg"]
        print(f"  -> DELTA (JH - baseline) : vitesse A={delta_speed:+.2f}mois, "
              f"solde_neg={delta_risk:+.2f}pts, profit={((row_jh['profit_moy']/row_base['profit_moy'])-1)*100:+.2f}%", flush=True)

        pd.DataFrame(rows).to_csv("chantier_pivot_jacksonhole_2026-08-23.csv", index=False)

    print(f"\n{'='*95}\nSYNTHESE\n{'='*95}")
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()

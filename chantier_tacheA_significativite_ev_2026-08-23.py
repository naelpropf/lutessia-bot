"""chantier_tacheA_significativite_ev_2026-08-23.py

TACHE A (session du 23/08) : test de significativite directe H0: EV=0 vs
H1: EV>0, sur r_multiples bruts (pas train/test), sur B_tradable_pgp
(n=1248, r_trailing corrige) ET A-seule (n=742, r_trailing corrige) --
memes populations que celles qui ont servi a refermer §6.5 (Point D n=600).

Methode :
- one-sample t-test standard (scipy.stats.ttest_1samp, H1 unilaterale >0)
- robustesse a la queue : moyenne winsorisee 5%/10% (scipy.stats.mstats.
  winsorize) et moyenne tronquee 5%/10% (scipy.stats.trim_mean)
- intervalle de confiance PAR BLOCK BOOTSTRAP (blocs calendaires de 2 mois,
  meme convention que real_cash_risk_year1_block_bootstrap.py partout
  ailleurs dans ce projet), PAS d'intervalle gaussien theorique -- 5000
  iterations (meme convention que registre_strategie_trading.md:1676,
  "IC95% bootstrap 5000 iterations")
- par bloc (1/2/3/4, memes bornes que chantier_fenetres_macro_chocs_2026-
  08-23.py::common_bloc_edges, deja etabli et utilise toute la session) EN
  PLUS du global
"""
import importlib.util

import numpy as np
import pandas as pd
from scipy import stats as sps

_spec = importlib.util.spec_from_file_location("chocs", "chantier_fenetres_macro_chocs_2026-08-23.py")
chocs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(chocs)

BLOCK_DAYS = 60  # 2 mois, convention projet (real_cash_risk_year1_block_bootstrap.py)
N_BOOT = 5000
RNG_SEED = 20260823


def block_bootstrap_ci(dates, values, stat_fn, n_boot=N_BOOT, seed=RNG_SEED, alpha=0.05):
    """CI par block bootstrap calendaire : decoupe (dates,values) tries en blocs
    CONTIGUS de BLOCK_DAYS jours depuis le premier trade, puis rechantillonne des
    BLOCS ENTIERS avec remise (meme nombre de blocs que l'original a chaque
    replicat) pour construire la distribution d'echantillonnage de stat_fn."""
    order = np.argsort(dates.values)
    d = dates.values[order]
    v = np.asarray(values)[order]
    t0 = d[0]
    block_idx = ((d - t0) / np.timedelta64(1, "D") // BLOCK_DAYS).astype(int)
    blocks = [v[block_idx == b] for b in np.unique(block_idx)]
    blocks = [b for b in blocks if len(b) > 0]
    n_blocks = len(blocks)
    rng = np.random.default_rng(seed)
    boot_stats = np.empty(n_boot)
    for i in range(n_boot):
        chosen = rng.integers(0, n_blocks, size=n_blocks)
        sample = np.concatenate([blocks[c] for c in chosen])
        boot_stats[i] = stat_fn(sample)
    lo, hi = np.percentile(boot_stats, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return lo, hi, n_blocks


def winsorized_mean(v, frac):
    from scipy.stats.mstats import winsorize
    return float(np.mean(winsorize(v, limits=(frac, frac))))


def trimmed_mean(v, frac):
    return float(sps.trim_mean(v, frac))


def analyze_series(dates, values, label):
    v = np.asarray(values, dtype=float)
    n = len(v)
    raw_mean = v.mean()
    t_stat, p_two = sps.ttest_1samp(v, 0.0)
    p_one = p_two / 2 if t_stat > 0 else 1 - p_two / 2

    stats_fns = {
        "raw": lambda x: x.mean(),
        "winsor5": lambda x: winsorized_mean(x, 0.05),
        "winsor10": lambda x: winsorized_mean(x, 0.10),
        "trim5": lambda x: trimmed_mean(x, 0.05),
        "trim10": lambda x: trimmed_mean(x, 0.10),
    }
    print(f"\n  -- {label} (n={n}) --")
    print(f"    t-test 1 echantillon H0:EV=0 vs H1:EV>0 : t={t_stat:.3f}, p(unilateral)={p_one:.6f}, "
          f"{'SIGNIFICATIF (p<0.05)' if p_one < 0.05 else 'NON significatif'}")
    row = dict(label=label, n=n, t_stat=t_stat, p_one_sided=p_one)
    for name, fn in stats_fns.items():
        point = fn(v)
        lo, hi, n_blocks = block_bootstrap_ci(dates, v, fn)
        excludes_zero = lo > 0
        print(f"    {name:10s} point={point:+.4f}R  CI95%[block-bootstrap, {n_blocks} blocs, {N_BOOT} iter]="
              f"[{lo:+.4f}, {hi:+.4f}]  {'EXCLUT 0 (signif.)' if excludes_zero else 'inclut 0 (non signif.)'}")
        row[f"{name}_point"] = point
        row[f"{name}_ci_lo"] = lo
        row[f"{name}_ci_hi"] = hi
        row[f"{name}_excludes_zero"] = excludes_zero
    return row


def run_population(pop, pop_label, edges):
    print(f"\n{'='*95}\nPOPULATION {pop_label} (n={len(pop)}, {pop['date_creation'].min()} -> {pop['date_creation'].max()})\n{'='*95}")
    rows = []
    rows.append(analyze_series(pop["date_creation"], pop["r_trailing"], f"{pop_label} GLOBAL"))
    for i in range(4):
        lo_e, hi_e = edges[i], edges[i + 1]
        bloc = pop[(pop["date_creation"] >= lo_e) & (pop["date_creation"] < hi_e)]
        if len(bloc) < 5:
            print(f"\n  -- bloc{i+1} : n={len(bloc)} trop petit, ignore --")
            continue
        rows.append(analyze_series(bloc["date_creation"], bloc["r_trailing"], f"{pop_label} bloc{i+1}"))
    return rows


def main():
    pop_a = chocs.load_pop_a()
    pop_b = chocs.load_pop_b()
    edges = chocs.common_bloc_edges(pop_a, pop_b)
    print("Bloc edges (communs A/B, deja etablis cette session) :", list(edges))

    all_rows = []
    all_rows += run_population(pop_b, "B_tradable_pgp", edges)
    all_rows += run_population(pop_a, "A_seule", edges)

    print(f"\n{'='*95}\nSYNTHESE\n{'='*95}")
    df = pd.DataFrame(all_rows)
    for _, r in df.iterrows():
        raw_sig = "OUI" if r["raw_excludes_zero"] else "non"
        w10_sig = "OUI" if r["winsor10_excludes_zero"] else "non"
        t10_sig = "OUI" if r["trim10_excludes_zero"] else "non"
        print(f"  {r['label']:22s} n={int(r['n']):4d} EV_brut={r['raw_point']:+.3f}R p(t-test)={r['p_one_sided']:.5f} | "
              f"CI_brut_excl0={raw_sig} CI_winsor10_excl0={w10_sig} CI_trim10_excl0={t10_sig}")

    df.to_csv("chantier_tacheA_significativite_ev_detail_2026-08-23.csv", index=False)


if __name__ == "__main__":
    main()

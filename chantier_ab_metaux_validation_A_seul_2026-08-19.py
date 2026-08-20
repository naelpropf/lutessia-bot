"""Validation rapide : le moteur double-flotte (chantier_ab_metaux_cascade_
officiel_2026-08-19.py) doit reproduire approximativement la reference
officielle S1.8 (COMBINE_corrige) quand B est desactive (population vide).
n modeste (RNG differente de S1.8 donc pas un match exact attendu, juste
un ordre de grandeur coherent) avant d'engager le run complet A+B."""
import importlib.util
import random
import time

import numpy as np
import pandas as pd

_spec = importlib.util.spec_from_file_location("abm", "chantier_ab_metaux_cascade_officiel_2026-08-19.py")
abm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(abm)

import etape_e_fleet_integration as ei
from monte_carlo_simulation import precompute_correlation_pairs

n_sims = 30
ceiling = 3000.0
seed = 9999

pop_A, market_data, excluded_map_A = abm.load_common_A()
all_tickers = sorted(pop_A["ticker"].unique())
corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
excluded_map = precompute_correlation_pairs(all_tickers, corr_matrix, abm.CORR_TH_NEW)
seq = ei.seq_grouped_multi(1000, 15000, 25000, 25000)
config = ei.CONFIG_REF

block_seconds = 2 * 30 * 86400
rng_wr = random.Random(seed)
rng_boot = random.Random(seed + 1)
rng_block = random.Random(seed + 2)
recs = []
t0 = time.time()
for _ in range(n_sims):
    wr = rng_wr.betavariate(abm.ALPHA_POST, abm.BETA_POST)
    trades_A, slots_A = abm.build_flexible_population_with_rr(pop_A, wr, 1.0, False, random.Random(rng_boot.random()))
    n_blocks = int(slots_A[-1] // block_seconds) + 1
    blocks_A = [[] for _ in range(n_blocks)]
    for tr, t in zip(trades_A, slots_A):
        idx = int(t // block_seconds)
        blocks_A[idx].append((tr, t - idx * block_seconds))
    target_duration = slots_A[-1]
    raw_t, raw_s = [], []
    cursor = 0.0
    while cursor < target_duration:
        idx = rng_block.randrange(n_blocks)
        for trade, offset in blocks_A[idx]:
            raw_t.append(trade); raw_s.append(cursor + offset)
        cursor += block_seconds
    res = abm.run_dual_ab(raw_t, raw_s, [], [], market_data, excluded_map,
                           ceiling, seq, config, ei.DEFAULT_EMERGENCY, metal_set=set())
    recs.append(res)

df = pd.DataFrame(recs)
combined_net_A_only = df["A_net"] - df["A_is_paid"]
year1_neg_A = df["A_year1_net"] < 0
print(f"[VALIDATION A-seul, moteur double-flotte, B desactive, n={n_sims}, plafond={ceiling:.0f}$] "
      f"({time.time()-t0:.0f}s)")
print(f"  profit_moyen A = {combined_net_A_only.mean():+,.0f}$  profit_median = {combined_net_A_only.median():+,.0f}$")
print(f"  annee1<0 A = {year1_neg_A.mean()*100:.2f}%")
print(f"  hit_ceiling (combine, mais B vide donc = A seul) = {df['combined_hit_ceiling'].mean()*100:.2f}%")
print(f"\n  Reference officielle S1.8 COMBINE_corrige @3000$ (registre) : annee1<0 ~15,50% (citee par l'utilisateur)")
print(f"  -> Comparaison d'ORDRE DE GRANDEUR seulement (seed/rng differents, n petit) avant d'engager le run A+B complet.")

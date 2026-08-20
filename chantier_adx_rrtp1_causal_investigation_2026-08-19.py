"""Investigation causale : pourquoi ADX>32,27 et rr_tp1<=1,25-sizing
detruisent du profit en Monte Carlo fleet (Config 2, B+metaux) malgre un
signal statistique propre. Reutilise integralement les fonctions du retest
(chantier_gold_silver_adx_sizing_retest_2026-08-19.py) -- aucune nouvelle
logique ADX/sizing, uniquement de l'analyse sur les memes objets."""
import importlib.util

import numpy as np
import pandas as pd

_spec = importlib.util.spec_from_file_location("gsr", "chantier_gold_silver_adx_sizing_retest_2026-08-19.py")
gsr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gsr)

ADX_TH = gsr.ADX_TH
RR_TP1_TH = gsr.RR_TP1_SIZING_TH
RR_TP2_TH = 8.0  # seuil S2.35 deja adopte

print("Chargement population B Config 2 baseline (identique Config 0, 1505 trades)...")
pop_B = pd.read_csv("chantier_gold_silver_pop_B_config0_2026-08-19.csv")
oa_all = pd.read_csv("chantier_gold_silver_pop_metaux_all_2026-08-19.csv")
metal_set = set(oa_all["ticker"].unique())
pop_B["date_creation"] = pd.to_datetime(pop_B["date_creation"])
pop_B["resolution_time_est"] = pd.to_datetime(pop_B["resolution_time_est"])

is_metal = pop_B["ticker"].isin(metal_set)
pop_B_fximd = pop_B[~is_metal].copy()
pop_B_metaux = pop_B[is_metal].copy()
print(f"B forex/indices : {len(pop_B_fximd)} | B metaux : {len(pop_B_metaux)}")

print("\nRecalcul ADX(14) -- memes fonctions EXACTES que le retest (build_candles_with_adx_*+compute_adx_at_entry)...")
candles_fx = gsr.build_candles_with_adx_forex_indices(pop_B_fximd)
pop_B_fximd = gsr.compute_adx_at_entry(pop_B_fximd, candles_fx)
candles_metaux = gsr.build_candles_with_adx_metaux(pop_B_metaux)
pop_B_metaux = gsr.compute_adx_at_entry(pop_B_metaux, candles_metaux)

pop = pd.concat([pop_B_fximd, pop_B_metaux], ignore_index=True).sort_values("date_creation").reset_index(drop=True)
n = len(pop)
print(f"[verif] population totale : {n}, ADX couvert : {pop['adx_at_entry'].notna().sum()}")

excl_adx = pop["adx_at_entry"] > ADX_TH
seg_rrtp1 = pop["rr_tp1"] <= RR_TP1_TH
seg_rrtp2_high = pop["rr_tp2"] >= RR_TP2_TH

print(f"\n{'='*78}\nPOINT 1 -- Chevauchement avec rr_tp2>={RR_TP2_TH} (levier deja adopte S2.35)\n{'='*78}")
base_rate_rrtp2 = seg_rrtp2_high.mean()
print(f"Taux de base rr_tp2>={RR_TP2_TH} sur toute la population B : {base_rate_rrtp2*100:.2f}% ({seg_rrtp2_high.sum()}/{n})")

for name, mask in [("ADX-exclu (adx_at_entry>32,27)", excl_adx), ("rr_tp1<=1,25 (downsize x0,7)", seg_rrtp1)]:
    sub = pop[mask]
    n_sub = len(sub)
    if n_sub == 0:
        print(f"\n[{name}] segment vide (couverture ADX insuffisante ?)")
        continue
    rate = (sub["rr_tp2"] >= RR_TP2_TH).mean()
    # test proportion (approx normale, z-test 2 proportions independantes)
    p1, p2 = rate, base_rate_rrtp2
    n1, n2 = n_sub, n
    p_pool = (sub["rr_tp2"].ge(RR_TP2_TH).sum() + seg_rrtp2_high.sum()) / (n1 + n2)
    se = np.sqrt(p_pool * (1 - p_pool) * (1/n1 + 1/n2)) if p_pool not in (0, 1) else np.nan
    z = (p1 - p2) / se if se and se > 0 else np.nan
    ratio = rate / base_rate_rrtp2 if base_rate_rrtp2 > 0 else np.nan
    print(f"\n[{name}] n={n_sub}/{n} ({n_sub/n*100:.1f}% de la pop) -- "
          f"taux rr_tp2>={RR_TP2_TH} dans le segment : {rate*100:.2f}% "
          f"vs base {base_rate_rrtp2*100:.2f}% -- ratio x{ratio:.2f} -- z={z:.2f}")

print(f"\n{'='*78}\nPOINT 2 -- Contribution a la queue de distribution (r_trailing = outcome_r)\n{'='*78}")
pop_sorted = pop.sort_values("r_trailing", ascending=False).reset_index(drop=True)
total_profit_r = pop["r_trailing"].sum()
print(f"Somme totale r_trailing (proxy profit population) : {total_profit_r:.1f}R sur {n} trades")

for pct in (0.01, 0.05):
    k = max(1, int(round(n * pct)))
    top = pop_sorted.iloc[:k]
    top_sum = top["r_trailing"].sum()
    share_profit = top_sum / total_profit_r * 100
    print(f"\n-- Top {pct*100:.0f}% par r_trailing (n={k}) : contribue {share_profit:.1f}% du profit total "
          f"(part en nombre de trades = {pct*100:.0f}% par construction)")
    for name, mask in [("ADX-exclu", excl_adx), ("rr_tp1<=1,25", seg_rrtp1)]:
        seg_idx = set(pop.index[mask])
        top_idx = set(pop_sorted.iloc[:k].index)
        n_overlap = len(seg_idx & top_idx)
        seg_share_in_pop = mask.mean()
        seg_share_in_top = n_overlap / k
        print(f"   [{name}] {n_overlap}/{k} trades du top{pct*100:.0f}% appartiennent au segment "
              f"({seg_share_in_top*100:.1f}% du top) vs {seg_share_in_pop*100:.1f}% de part dans la pop totale "
              f"-- {'SUR' if seg_share_in_top > seg_share_in_pop else 'SOUS'}-represente x{seg_share_in_top/seg_share_in_pop if seg_share_in_pop>0 else float('nan'):.2f}")

# EV moyenne par segment vs reste, pour situer "statistiquement plus faible en moyenne" vs "queue"
print(f"\n{'='*78}\nComplement : EV moyenne (r_trailing) segment vs reste de la population\n{'='*78}")
for name, mask in [("ADX-exclu", excl_adx), ("rr_tp1<=1,25", seg_rrtp1)]:
    seg = pop[mask]["r_trailing"]
    rest = pop[~mask]["r_trailing"]
    print(f"[{name}] EV segment={seg.mean():+.3f}R (n={len(seg)}) vs EV reste={rest.mean():+.3f}R (n={len(rest)}) -- "
          f"mediane segment={seg.median():+.3f}R vs mediane reste={rest.median():+.3f}R")

pop.to_csv("chantier_adx_rrtp1_causal_population_with_adx_2026-08-19.csv", index=False)
print("\nSauvegarde population annotee (adx_at_entry inclus) : chantier_adx_rrtp1_causal_population_with_adx_2026-08-19.csv")

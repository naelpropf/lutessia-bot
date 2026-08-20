"""
Point 5 (session 18/08->19/08) -- balayage du plafond de capital personnel
de 10 000$ a 200 000$ sous la config REF actuelle complete (RR>=1,35,
any-RR, correctif risque Instant 1,5%, rr_tp2 §2.35), pour identifier le
point de plateau au-dela duquel l'apport de capital supplementaire
n'apporte plus de gain mesurable.

Rappel deja etabli (session 08/17, registre_parametres_projet.md #10) :
a 3000$/5000$, bb_threshold=0 (Instant partout des le depart) est deja la
config optimale, et 2500$ egale deja 3000$/5000$ au $ pres -- le plateau
bas est situe entre 2000$ et 2500$. Ce script part de 10 000$ (bien
au-dela de cette zone de transition) donc bb_threshold=0 est utilise
PARTOUT dans ce balayage (pas de nouvelle transition attendue a ces
plafonds, coherent avec le regime "Instant partout" deja domine).

Reutilise chantier_S1_8_officiel_n600_risque_corrige_2026-08-17.py via
importlib (meme garde-fou population forex-only que Points 2/3/4).

N'importe pas ce script directement (convention du projet).
"""
import importlib.util
import sys
import time

import pandas as pd

REF_SCRIPT = "chantier_S1_8_officiel_n600_risque_corrige_2026-08-17.py"

spec = importlib.util.spec_from_file_location("ref_s18_p5", REF_SCRIPT)
ref = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ref)

INDEX_KEYWORDS = ["DAX40", "S&P500", "NASDAQ100", "DJ30"]


def load_common_forex_only():
    pop, market_data, excluded_map = ref.load_common()
    is_index = pop["ticker"].str.contains("|".join(INDEX_KEYWORDS), case=False, na=False)
    n_before = len(pop)
    pop = pop[~is_index].reset_index(drop=True)
    if len(pop) != n_before:
        tickers = sorted(pop["ticker"].unique())
        excluded_map = ref.precompute_correlation_pairs(
            tickers, pd.read_csv("correlation_matrix.csv", index_col=0), ref.CORR_TH_NEW)
    return pop, market_data, excluded_map


if __name__ == "__main__":
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    ceilings_arg = ([float(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else
                     [10000.0, 20000.0, 30000.0, 40000.0, 50000.0, 75000.0, 100000.0, 150000.0, 200000.0])

    t_start = time.time()
    pop, market_data, excluded_map = load_common_forex_only()
    print(f"[verif] population REF (forex-only) : {len(pop)} trades")

    seq = ref.ei.seq_grouped_multi(1000, 15000, 25000, 25000)
    config = ref.ei.CONFIG_REF
    common_kwargs = dict(emergency=ref.ei.DEFAULT_EMERGENCY, eval_risk=ref.EVAL_RISK, fleet_risk=ref.FLEET_RISK,
                          gft_eval_risk=ref.GFT_EVAL_RISK, reserve_share=ref.ei.FINAL_RESERVE_SHARE,
                          extra_threshold_mult=ref.ei.EXTRA_THRESHOLD_MULT, n_sims=n_sims, seed=9999,
                          b_entry_frac=0.20, b_reduction=0.5, pre_unlock_only=True,
                          ftmo_discount=True, gft_goat_guard=True, payout_cycle=True,
                          use_any_rr=True, apply_instant_risk_cap=True)

    rows = []
    prev_profit = None
    for ceiling in ceilings_arg:
        t0 = time.time()
        df = ref.run_propagated(pop, market_data, excluded_map, ceiling, seq, config,
                                 bb_threshold=0.0, **common_kwargs)
        row = ref.summarize(df, f"ceiling_{ceiling:.0f}", ceiling, 0.0, True)
        rows.append(row)
        d_txt = ""
        if prev_profit is not None:
            d_txt = f" (delta vs precedent : {(row['profit_moyen']-prev_profit)/abs(prev_profit)*100:+.2f}%)"
        prev_profit = row["profit_moyen"]
        print(f"[plafond={ceiling:>9,.0f}$] profit_moy={row['profit_moyen']:+,.0f}$ "
              f"solde_neg={row['solde_negatif_annee4']:.2f}% hit_ceiling={row['hit_ceiling_pct']:.2f}% "
              f"annee1<0={row['annee1_neg']:.2f}%{d_txt} ({time.time()-t0:.0f}s)")
        pd.DataFrame(rows).to_csv(f"chantier_p5_capital_ceiling_sweep_n{n_sims}_2026-08-19.csv", index=False)

    print(f"\nTermine en {time.time()-t_start:.0f}s.")

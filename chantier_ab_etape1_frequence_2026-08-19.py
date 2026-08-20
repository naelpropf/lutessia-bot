"""
Chantier moteur joint A+B, Etape 1 -- risque de frequence (validation de
phase / inactivite), session 2026-08-19.

Reutilise TEL QUEL :
- FORMATS (engine_multiformat.py:62-239, source etape_a_formats_comptes_
  propfirms_2026-08-08.md) pour les regles min_days/DD par phase/firm.
- make_acc_mf/process_trade_mf (engine_multiformat.py:246-390) pour la
  logique de validation de phase (aucune reimplementation).
- build_pop_B_variant (chantier_b6_montecarlo_2026-08-19.py:728-752,
  meme construction que le Monte Carlo fleet B de cette session), trailing
  0.10x (confirme n=600, session_handoff_2026-08-19.md).
- build_blocks / build_full_block_bootstrap_sequence (real_cash_risk_
  year1_block_bootstrap.py:35-49, reference_metrics_final.py:55-64),
  bootstrap par blocs 2 mois -- meme convention que le reste du projet.

Verification frequence B vs A (mesuree directement, PAS supposee) :
- A (742 trades, registre_parametres_projet.md:673) : 13,77 trades/mois.
- B (571 trades, build_pop_B_variant(0.10)) : mesure ci-dessous, span
  quasi identique a A (~4,5 ans) -- ratio B/A mesure directement, pas la
  valeur 63,4% citee dans le prompt (ecart note, pas reconcilie -- utilise
  la valeur mesuree, reproductible depuis ce script).

Recherche 08/06-08/07 (etape_a_formats_comptes_propfirms_2026-08-08.md,
cf. engine_multiformat.py confidence_notes) : AUCUNE regle d'inactivite
(delai max sans trade avant fermeture/flag du compte) n'a ete documentee
pour aucune firm -- gap de recherche reel, pas comble ici par supposition.
Seule proxy disponible : distance temporelle reelle entre trades B
consecutifs (mesuree ci-dessous), a comparer manuellement si une regle
d'inactivite est trouvee plus tard.
"""
import random
import time

import numpy as np
import pandas as pd
import importlib.util

import robustness_5ers_risk_challenge as eng
from monte_carlo_simulation import precompute_correlation_pairs
from scaling_simulation import CORR_THRESHOLD, load_market_data
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH
from reference_metrics_final import build_full_block_bootstrap_sequence
from engine_multiformat import FORMATS, make_acc_mf, process_trade_mf

DAY_SECONDS = 86400
YEAR_SECONDS = 365.25 * DAY_SECONDS
BLOCK_MONTHS = 2
BLOCK_SECONDS = BLOCK_MONTHS * DAYS_PER_MONTH * DAY_SECONDS
N_SCREEN = 300

_spec = importlib.util.spec_from_file_location("b6", "chantier_b6_montecarlo_2026-08-19.py")
b6 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(b6)


def build_trades_B(trailing_factor=0.10):
    pop = b6.build_pop_B_variant(trailing_factor=trailing_factor)
    pop = pop.sort_values("date_creation").reset_index(drop=True)
    t0 = pop["date_creation"].iloc[0]
    slot_arrivals = [(d - t0).total_seconds() for d in pop["date_creation"]]
    trades = []
    for _, row in pop.iterrows():
        outcome_r = row["r_trailing"] if row["statut_final"] == "OBJECTIF ATTEINT" else -1.0
        trades.append({
            "ticker": row["ticker"],
            "outcome_r": float(outcome_r),
            "sl_distance": abs(row["prix_entree"] - row["stop_loss_init"]),
            "hold_seconds": (row["resolution_time_est"] - row["date_creation"]).total_seconds(),
            "rr_tp1": float(row["rr_tp1"]),
        })
    return pop, trades, slot_arrivals


def gap_stats(slot_arrivals):
    gaps_days = np.diff(sorted(slot_arrivals)) / DAY_SECONDS
    return dict(median=np.median(gaps_days), p90=np.percentile(gaps_days, 90),
                p99=np.percentile(gaps_days, 99), max=gaps_days.max())


def time_to_fund_one_run(fmt, trades, slot_arrivals, blocks, market_data, excluded_map, rng,
                          risk_pct, horizon_seconds):
    synth_trades, synth_slots = build_full_block_bootstrap_sequence(blocks, BLOCK_SECONDS, rng, horizon_seconds)
    palier = 25_000
    acc = make_acc_mf(fmt, palier, cost=0.0, active=True)
    state = {"reserve": 1e12, "total_breaks": 0}  # reserve illimitee : isole le risque de TEMPS, pas le cash
    if acc["phase"] == "funded":
        return 0.0, 0  # instant funding : finance des l'ouverture, temps=0
    for trade, now in zip(synth_trades, synth_slots):
        just_funded = process_trade_mf(acc, trade, now, fmt, state, risk_pct, market_data, excluded_map)
        if just_funded:
            return now / DAY_SECONDS, acc["trades_taken"]
    return None, acc["trades_taken"]  # jamais finance dans l'horizon teste


if __name__ == "__main__":
    t_start = time.time()
    pop_B, trades_B, slot_arrivals_B = build_trades_B(0.10)
    freq_B = len(trades_B) / (slot_arrivals_B[-1] / DAY_SECONDS) * DAYS_PER_MONTH
    freq_A = 13.77  # registre_parametres_projet.md:673
    print(f"B : n={len(trades_B)}, span={slot_arrivals_B[-1]/DAY_SECONDS:.0f}j, freq={freq_B:.2f}/mois")
    print(f"A (registre) : freq={freq_A:.2f}/mois")
    print(f"Ratio B/A mesure : {100*freq_B/freq_A:.1f}% (vs 63,4% cite dans le prompt -- ecart non reconcilie)")

    g = gap_stats(slot_arrivals_B)
    print(f"\nEcart entre trades B consecutifs (jours) : median={g['median']:.2f} p90={g['p90']:.2f} "
          f"p99={g['p99']:.2f} max={g['max']:.1f}")
    print("(Aucune regle d'inactivite documentee trouvee pour comparaison -- gap de recherche reel.)")

    market_data = b6.build_market_data_with_indices()  # forex + entrees "unconstrained" indices
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(set(t["ticker"] for t in trades_B))
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)
    blocks = build_blocks(trades_B, slot_arrivals_B, BLOCK_SECONDS)
    horizon_seconds = 2 * YEAR_SECONDS  # generous : 2 ans, largement au-dela de tout format eval realiste

    candidates = ["Blueberry_InstantElite", "Blueberry_2StepStandard", "GFT_2Step_GOAT", "FTMO_2Step_Swing"]
    print(f"\n=== Temps de validation de phase B seule, n={N_SCREEN} runs/format ===")
    for fmt_key in candidates:
        fmt = FORMATS[fmt_key]
        rng = random.Random(4242)
        days_list, never = [], 0
        for _ in range(N_SCREEN):
            days, _ = time_to_fund_one_run(fmt, trades_B, slot_arrivals_B, blocks, market_data, excluded_map,
                                            rng, risk_pct=1.90, horizon_seconds=horizon_seconds)
            if days is None:
                never += 1
            else:
                days_list.append(days)
        if days_list:
            print(f"  {fmt_key:26s} min_days/phase={[p['min_days'] for p in fmt['phases']]} "
                  f"temps-a-financement (jours) p10/p50/p90={np.percentile(days_list,10):.0f}/"
                  f"{np.percentile(days_list,50):.0f}/{np.percentile(days_list,90):.0f} "
                  f"jamais-finance={100*never/N_SCREEN:.1f}%")
        else:
            print(f"  {fmt_key:26s} -- jamais finance dans l'horizon teste (100%)")
    print(f"\n({time.time()-t_start:.0f}s)")

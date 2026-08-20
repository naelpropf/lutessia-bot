"""
Point 2 (session 18/08->19/08) -- diagnostic + quantification : une fois la
cible de profit de phase atteinte (cumulative_since_reset >= target_pct),
le moteur (engine_multiformat.py:375-388) continue-t-il a faire trader le
compte tant que le minimum de jours de trading (min_days, compte des jours
DISTINCTS avec au moins un trade -- pas des jours calendaires) n'est pas
atteint ?

Citation exacte (engine_multiformat.py:375-388) :
    if acc["phase"] == "challenge" and pdef["target_pct"] is not None:
        days_ok = pdef["min_days"] is None or len(acc["trading_days_since_reset"]) >= pdef["min_days"]
        if acc["cumulative_since_reset"] >= pdef["target_pct"] / 100 * acc["palier"] and days_ok:
            ... avance de phase ...
        return False
-- si cumulative>=target MAIS days_ok=False, la fonction retourne False SANS
avancer de phase NI modifier acc["active"] : le compte reste "challenge",
phase_index inchange, et continuera a recevoir tous les signaux routes vers
lui au risque_pct PLEIN configure (aucune branche de pause/gel n'existe
dans le moteur). AUCUN mecanisme de blocage/reduction de risque n'existe
pour cette fenetre -- confirme par lecture exhaustive de process_trade_mf
(aucune reference a "waiting"/"pause"/"freeze" dans tout engine_multiformat.py).

Ce script :
1. DIAGNOSTIC (n=600, REF actuel, comportement INCHANGE) : instrumente
   process_trade_mf pour compter, sur les comptes en "challenge", les
   trades pris APRES que la cible ait ete atteinte mais AVANT que days_ok
   ne soit vrai ("fenetre d'attente"), et combien de ces trades causent une
   casse (daily_broke ou max_broke) qui n'aurait pas eu lieu a risque quasi
   nul.
2. QUANTIFICATION (n=600, variante MITIGEE) : meme moteur, meme population,
   meme seed, SEULE difference -- risk_pct force a un epsilon quasi nul
   (0.01%, symbolise "1 micro-lot juste pour valider le jour", pas 0.0 exact
   pour eviter tout comportement degenere division/volume) pendant la
   fenetre d'attente. Compare profit/hit_ceiling/annee1<0/solde_neg contre
   le REF baseline (meme run diagnostic, comportement inchange = REF exact),
   aux 4 plafonds 960$/1000$/3000$/5000$.

Reutilise integralement chantier_S1_8_officiel_n600_risque_corrige_2026-08-17.py
(script backant la reference officielle S1.8) via importlib (nom de fichier
avec tirets, pas important comme module standard) -- AUCUNE duplication de
la logique de simulation, seul process_trade_mf est enveloppe.

N'importe pas ce script directement (convention du projet).
"""
import importlib.util
import sys
import time

import pandas as pd

REF_SCRIPT = "chantier_S1_8_officiel_n600_risque_corrige_2026-08-17.py"
WAITING_RISK_PCT = 0.01  # micro-lot symbolique, pas 0.0 exact

spec = importlib.util.spec_from_file_location("ref_s18_p2", REF_SCRIPT)
ref = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ref)

_orig_process_trade_mf = ref.process_trade_mf
_current_phase = ref._current_phase

DIAG = {"waiting_trades": 0, "waiting_breaks": 0, "accounts_entering_window": 0}
MITIGATE = {"on": False}


def _in_waiting_window(acc, fmt):
    pdef = _current_phase(fmt, acc)
    if acc["phase"] != "challenge" or pdef["target_pct"] is None:
        return False
    target_reached = acc["cumulative_since_reset"] >= pdef["target_pct"] / 100 * acc["palier"]
    days_ok = pdef["min_days"] is None or len(acc["trading_days_since_reset"]) >= pdef["min_days"]
    return target_reached and not days_ok


def process_trade_mf_diag(acc, trade, now, fmt, state, risk_pct, market_data, excluded_map, **kw):
    in_window_before = _in_waiting_window(acc, fmt)
    days_before = len(acc["trading_days_since_reset"])
    if in_window_before:
        DIAG["waiting_trades"] += 1
        if days_before == 0 or acc.get("_last_seen_window_id") != id(acc):
            pass
        breaks_before = state["total_breaks"]
        eff_risk = WAITING_RISK_PCT if MITIGATE["on"] else risk_pct
    else:
        eff_risk = risk_pct
    result = _orig_process_trade_mf(acc, trade, now, fmt, state, eff_risk, market_data, excluded_map, **kw)
    if in_window_before and state["total_breaks"] > breaks_before:
        DIAG["waiting_breaks"] += 1
    return result


ref.process_trade_mf = process_trade_mf_diag


INDEX_KEYWORDS = ["DAX40", "S&P500", "NASDAQ100", "DJ30"]


def load_common_forex_only():
    """<<< 2026-08-19 : build_population_with_trailing() inclut desormais les
    indices automatiquement (correctif rr_threshold_test.py:43-61 du 08/18),
    mais eng.load_market_data() (donnees marche REELLES utilisees par la
    reference officielle S1.8) ne couvre PAS les indices -- confirme par
    KeyError direct en test de fumee (NASDAQ100 absent). La reference
    officielle §1.8 n'a PAS encore ete regeneree avec la population elargie
    (point ouvert #2 du handoff 08/18, marche pas de decision utilisateur) --
    donc reproduire ici la population forex-only actuellement officielle,
    par filtrage explicite, plutot que de laisser un crash silencieux ou une
    population non documentee se glisser dans ce diagnostic."""
    pop, market_data, excluded_map = ref.load_common()
    is_index = pop["ticker"].str.contains("|".join(INDEX_KEYWORDS), case=False, na=False)
    n_before = len(pop)
    pop = pop[~is_index].reset_index(drop=True)
    if len(pop) != n_before:
        print(f"[verif] population REF filtree forex-only : {n_before} -> {len(pop)} "
              f"({n_before-len(pop)} trades indices retires, coherent avec le point ouvert "
              f"'S1.8 pas encore regenere avec la population elargie')")
        tickers = sorted(pop["ticker"].unique())
        excluded_map = ref.precompute_correlation_pairs(tickers, pd.read_csv("correlation_matrix.csv", index_col=0), ref.CORR_TH_NEW)
    return pop, market_data, excluded_map


def run_variant(n_sims, ceilings, mitigate):
    MITIGATE["on"] = mitigate
    DIAG["waiting_trades"] = 0
    DIAG["waiting_breaks"] = 0
    pop, market_data, excluded_map = load_common_forex_only()
    seq = ref.ei.seq_grouped_multi(1000, 15000, 25000, 25000)
    config = ref.ei.CONFIG_REF
    common_kwargs = dict(emergency=ref.ei.DEFAULT_EMERGENCY, eval_risk=ref.EVAL_RISK, fleet_risk=ref.FLEET_RISK,
                          gft_eval_risk=ref.GFT_EVAL_RISK, reserve_share=ref.ei.FINAL_RESERVE_SHARE,
                          extra_threshold_mult=ref.ei.EXTRA_THRESHOLD_MULT, n_sims=n_sims, seed=9999,
                          b_entry_frac=0.20, b_reduction=0.5, pre_unlock_only=True,
                          ftmo_discount=True, gft_goat_guard=True, payout_cycle=True,
                          use_any_rr=True, apply_instant_risk_cap=True)
    BB_THRESHOLD_BY_CEILING = {960.0: 5000.0, 1000.0: 5000.0, 3000.0: 0.0, 5000.0: 0.0}
    rows = []
    for ceiling in ceilings:
        bb_th = BB_THRESHOLD_BY_CEILING[ceiling]
        t0 = time.time()
        df = ref.run_propagated(pop, market_data, excluded_map, ceiling, seq, config,
                                 bb_threshold=bb_th, **common_kwargs)
        label = "MITIGE" if mitigate else "REF_baseline"
        row = ref.summarize(df, label, ceiling, bb_th, True)
        rows.append(row)
        print(f"[{label:12s} plafond={ceiling:.0f}$] profit_moy={row['profit_moyen']:+,.0f}$ "
              f"solde_neg={row['solde_negatif_annee4']:.2f}% hit_ceiling={row['hit_ceiling_pct']:.2f}% "
              f"annee1<0={row['annee1_neg']:.2f}% ({time.time()-t0:.0f}s)")
    print(f"  [diag] fenetre-attente : {DIAG['waiting_trades']} trades pris cible-atteinte/jours-pas-ok, "
          f"{DIAG['waiting_breaks']} casses parmi eux "
          f"({DIAG['waiting_breaks']/DIAG['waiting_trades']*100 if DIAG['waiting_trades'] else 0:.2f}%)")
    return pd.DataFrame(rows), dict(DIAG)


if __name__ == "__main__":
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 300
    ceilings = [float(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [960.0, 1000.0, 3000.0, 5000.0]

    t_start = time.time()
    print("=" * 70)
    print("REF baseline (comportement actuel, INSTRUMENTE mais non modifie)")
    print("=" * 70)
    df_ref, diag_ref = run_variant(n_sims, ceilings, mitigate=False)

    print("\n" + "=" * 70)
    print("Variante MITIGEE (risk_pct quasi nul pendant la fenetre d'attente)")
    print("=" * 70)
    df_mit, diag_mit = run_variant(n_sims, ceilings, mitigate=True)

    print("\n" + "=" * 70)
    print("COMPARAISON REF vs MITIGE")
    print("=" * 70)
    for ceiling in ceilings:
        r = df_ref[df_ref["ceiling"] == ceiling].iloc[0]
        m = df_mit[df_mit["ceiling"] == ceiling].iloc[0]
        d_profit_pct = (m["profit_moyen"] - r["profit_moyen"]) / abs(r["profit_moyen"]) * 100
        print(f"  plafond={ceiling:.0f}$ : profit {r['profit_moyen']:+,.0f}$ -> {m['profit_moyen']:+,.0f}$ "
              f"({d_profit_pct:+.2f}%) | solde_neg {r['solde_negatif_annee4']:.2f}% -> {m['solde_negatif_annee4']:.2f}% "
              f"| hit_ceiling {r['hit_ceiling_pct']:.2f}% -> {m['hit_ceiling_pct']:.2f}% "
              f"| annee1<0 {r['annee1_neg']:.2f}% -> {m['annee1_neg']:.2f}% "
              f"(delta {m['annee1_neg']-r['annee1_neg']:+.2f}pt)")

    df_ref.to_csv(f"chantier_p2_dd_post_objectif_ref_n{n_sims}_2026-08-19.csv", index=False)
    df_mit.to_csv(f"chantier_p2_dd_post_objectif_mitige_n{n_sims}_2026-08-19.csv", index=False)
    print(f"\nTermine en {time.time()-t_start:.0f}s.")

"""
Recalcul consolidé des chiffres de référence les plus importants, avec les DEUX
correctifs établis aujourd'hui appliqués ensemble pour la première fois :
  1. Comptabilité FINANCÉ SEULEMENT (cf. sizing_fleet_test.py / mémoire projet) : le
     pnl généré PENDANT une tentative de challenge n'est jamais réel -- seul le pnl
     généré une fois le compte FINANCÉ compte comme profit réellement retirable. Le
     coût de rachat de challenge (couvert par la réserve en priorité, sinon poche
     perso) reste une dépense réelle, inchangé.
  2. BLOCK BOOTSTRAP à 2 mois (cf. real_cash_risk_year1_block_bootstrap.py) au lieu
     de la permutation individuelle -- préserve le regroupement temporel réel des
     périodes difficiles/favorables, révèle une queue de risque nettement plus grosse
     sur la trésorerie perso que la permutation ne le montrait.

Régime de risque VERROUILLÉ (pas remis en question ici) : 0.5%/compte jusqu'à ce que
la réserve commune atteigne 5000€, puis 2%/compte de façon irréversible (cf.
risk_switch_threshold_test.py, déclencheur "5. Réserve >= 5000€").

Payoff réaliste + trailing 0.2xSL (trailing_payoff_population), seuil rr_tp1>=1.5,
copytrade 3 comptes/3 firms, plafond 3 positions, corrélation 0.6+JPY, faisabilité
marge(1:30)/100 lots -- config de référence inchangée par ailleurs.

Livrables :
  A. Profit net FINANCÉ, par année (1, 2, 3, horizon complet ~3.96 ans) -- Monte
     Carlo 2000 runs, block bootstrap 2 mois.
  B. Rendement mensuel (%) -- trajectoire déterministe (chronologie réelle, comme
     partout ailleurs dans ce projet), sur la MÊME comptabilité financé-seulement.
  C. Risque de trésorerie perso en début de vie (année 1, réserve~0) -- reprend tel
     quel le résultat déjà obtenu par risk_switch_threshold_block_bootstrap.py au
     déclencheur 5000€ (déjà la bonne méthode : real_cash_paid n'a jamais eu le
     problème financé/challenge, seul le profit affiché à côté en manquait -- corrigé
     ici).
"""
import random

import pandas as pd

from scaling_simulation import (
    TIER_SEQUENCE, CHALLENGE_COST, UPGRADE_COST, CHALLENGE_TARGET_PCT,
    MIN_TRADING_DAYS, BREAK_DD_PCT, RESERVE_SHARE, MAX_POSITIONS, CORR_THRESHOLD,
    feasible_risk_pct, load_market_data,
)
from monte_carlo_simulation import precompute_correlation_pairs, N_SIMULATIONS
from trailing_payoff_population import build_population_with_trailing, build_trades_trailing
from real_cash_risk_year1_block_bootstrap import build_blocks, DAYS_PER_MONTH

LOW_RISK = 0.5
HIGH_RISK = 2.0
RESERVE_SWITCH_THRESHOLD = 5000.0  # régime verrouillé
N_ACCOUNTS = 3
YEAR_SECONDS = 365.25 * 86400
BLOCK_MONTHS = 2
YEAR_MARKS = [1, 2, 3]  # + horizon complet ajouté séparément


def build_full_block_bootstrap_sequence(blocks, block_seconds, rng, target_duration):
    synthetic_trades, synthetic_slots = [], []
    cursor = 0.0
    while cursor < target_duration:
        block = blocks[rng.randrange(len(blocks))]
        for trade, offset in block:
            synthetic_trades.append(trade)
            synthetic_slots.append(cursor + offset)
        cursor += block_seconds
    return synthetic_trades, synthetic_slots


def run_one_hybrid_funded(trades, slot_arrivals, market_data, excluded_map, order, year_marks_seconds):
    """Compte unique : risque LOW_RISK jusqu'à réserve>=RESERVE_SWITCH_THRESHOLD, puis
    HIGH_RISK de façon irréversible. Trace le pnl FINANCÉ SEULEMENT (jamais le pnl de
    challenge) + le cash réel payé, avec un instantané à chaque marque temporelle de
    year_marks_seconds (ex: [1an, 2ans, 3ans]), plus le total final."""
    palier = TIER_SEQUENCE[0]
    phase = "challenge"
    cumulative_since_reset = 0.0
    peak_since_reset = 0.0
    trading_days_since_reset = set()
    reserve = 0.0
    open_positions = []

    real_cash_paid = CHALLENGE_COST[palier]
    total_funded_pnl = 0.0
    total_fees_paid = CHALLENGE_COST[palier]
    switched = False

    marks_sorted = sorted(year_marks_seconds)
    mark_idx = 0
    snapshots = []  # (mark_seconds, funded_net_profit, real_cash_paid)

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]

        while mark_idx < len(marks_sorted) and now > marks_sorted[mark_idx]:
            snapshots.append((marks_sorted[mark_idx], total_funded_pnl - total_fees_paid, real_cash_paid))
            mark_idx += 1

        close_time = now + trade["hold_seconds"]
        open_positions = [(t, c) for (t, c) in open_positions if c > now]

        if len(open_positions) >= MAX_POSITIONS:
            continue
        if any(t in excluded_map[trade["ticker"]] for (t, _) in open_positions):
            continue

        current_risk = HIGH_RISK if switched else LOW_RISK
        effective_risk_pct, _ = feasible_risk_pct(trade["ticker"], trade["sl_distance"], palier, current_risk, market_data)
        risk_amount = effective_risk_pct / 100 * palier
        pnl = trade["outcome_r"] * risk_amount

        open_positions.append((trade["ticker"], close_time))
        cumulative_since_reset += pnl
        peak_since_reset = max(peak_since_reset, cumulative_since_reset)
        trading_days_since_reset.add(int(now // 86400))

        if phase == "funded":
            total_funded_pnl += pnl
            if pnl > 0:
                reserve += pnl * RESERVE_SHARE

        if not switched and reserve >= RESERVE_SWITCH_THRESHOLD:
            switched = True

        drawdown = peak_since_reset - cumulative_since_reset
        if drawdown >= BREAK_DD_PCT / 100 * palier:
            cost = CHALLENGE_COST[palier]
            if reserve >= cost:
                reserve -= cost
            else:
                real_cash_paid += cost - reserve
                reserve = 0.0
            total_fees_paid += cost
            phase = "challenge"
            cumulative_since_reset = 0.0
            peak_since_reset = 0.0
            trading_days_since_reset = set()
            continue

        if (phase == "challenge"
                and cumulative_since_reset >= CHALLENGE_TARGET_PCT / 100 * palier
                and len(trading_days_since_reset) >= MIN_TRADING_DAYS):
            phase = "funded"
            cumulative_since_reset = 0.0
            peak_since_reset = 0.0
            trading_days_since_reset = set()

        if phase == "funded":
            idx = TIER_SEQUENCE.index(palier)
            if idx + 1 < len(TIER_SEQUENCE):
                next_tier = TIER_SEQUENCE[idx + 1]
                cost = UPGRADE_COST[next_tier]
                if reserve >= cost:
                    reserve -= cost
                    total_fees_paid += cost
                    palier = next_tier
                    phase = "challenge"
                    cumulative_since_reset = 0.0
                    peak_since_reset = 0.0
                    trading_days_since_reset = set()

    while mark_idx < len(marks_sorted):
        snapshots.append((marks_sorted[mark_idx], total_funded_pnl - total_fees_paid, real_cash_paid))
        mark_idx += 1

    final_net_profit = total_funded_pnl - total_fees_paid
    return snapshots, final_net_profit, real_cash_paid


def run_copytrade_hybrid_funded_block(blocks, block_seconds, market_data, excluded_map, rng,
                                       year_marks_seconds, target_duration):
    synthetic_trades, synthetic_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, target_duration)
    identity_order = list(range(len(synthetic_trades)))

    combined_snapshots = None
    combined_final = 0.0
    combined_cash = 0.0
    for _ in range(N_ACCOUNTS):
        snaps, final_np, cash = run_one_hybrid_funded(
            synthetic_trades, synthetic_slots, market_data, excluded_map, identity_order, year_marks_seconds
        )
        if combined_snapshots is None:
            combined_snapshots = [0.0] * len(snaps)
        for i, (mark, np_, _) in enumerate(snaps):
            combined_snapshots[i] += np_
        combined_final += final_np
        combined_cash += cash

    return combined_snapshots, combined_final, combined_cash


def main():
    pop = build_population_with_trailing("fixed", 0.2, verbose=False)
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    sub, trades, slot_arrivals = build_trades_trailing(pop)
    tickers = sorted(set(t["ticker"] for t in trades))
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    total_horizon_seconds = slot_arrivals[-1]
    total_horizon_years = total_horizon_seconds / YEAR_SECONDS
    print(f"Horizon total de la population réelle : {total_horizon_years:.2f} ans "
          f"({total_horizon_seconds/86400/30.44:.1f} mois)")

    block_seconds = BLOCK_MONTHS * DAYS_PER_MONTH * 86400
    blocks = build_blocks(trades, slot_arrivals, block_seconds)

    year_marks_seconds = [y * YEAR_SECONDS for y in YEAR_MARKS]

    # === A. Profit net FINANCÉ par année (Monte Carlo, block bootstrap 2 mois) ===
    print("\n" + "=" * 100)
    print(f"A. PROFIT NET FINANCÉ PAR ANNÉE -- régime 0.5%->2% @ réserve 5000€, "
          f"block bootstrap {BLOCK_MONTHS} mois, {N_SIMULATIONS} runs")
    print("=" * 100)

    rng = random.Random(42)
    all_snapshots = []
    all_finals = []
    all_cash = []
    for _ in range(N_SIMULATIONS):
        snaps, final_np, cash = run_copytrade_hybrid_funded_block(
            blocks, block_seconds, market_data, excluded_map, rng, year_marks_seconds, total_horizon_seconds
        )
        all_snapshots.append(snaps)
        all_finals.append(final_np)
        all_cash.append(cash)

    for i, y in enumerate(YEAR_MARKS):
        vals = sorted(s[i] for s in all_snapshots)
        n = len(vals)
        mean_v, median_v, p5_v = sum(vals) / n, vals[n // 2], vals[int(0.05 * n)]
        pct_loss = sum(1 for v in vals if v < 0) / n * 100
        print(f"Fin année {y} : moyenne {mean_v:+,.0f}€ | médiane {median_v:+,.0f}€ | "
              f"p5 {p5_v:+,.0f}€ | P(perte) {pct_loss:.1f}%")

    finals_sorted = sorted(all_finals)
    n = len(finals_sorted)
    print(f"Fin horizon complet ({total_horizon_years:.2f} ans) : moyenne "
          f"{sum(finals_sorted)/n:+,.0f}€ | médiane {finals_sorted[n//2]:+,.0f}€ | "
          f"p5 {finals_sorted[int(0.05*n)]:+,.0f}€")

    pd.DataFrame({
        **{f"year{y}_funded_net_profit": [s[i] for s in all_snapshots] for i, y in enumerate(YEAR_MARKS)},
        "final_funded_net_profit": all_finals, "final_real_cash_paid": all_cash,
    }).to_csv("reference_metrics_final_detail.csv", index=False)

    # === B. Rendement mensuel (%) -- trajectoire déterministe, même comptabilité ===
    print("\n" + "=" * 100)
    print("B. RENDEMENT MENSUEL (%) -- trajectoire déterministe (chronologie réelle), "
          "profit financé seulement / palier combiné courant")
    print("=" * 100)

    natural_order = list(range(len(trades)))
    accounts_state = []
    for _ in range(N_ACCOUNTS):
        palier = TIER_SEQUENCE[0]
        accounts_state.append({
            "palier": palier, "phase": "challenge", "cumulative_since_reset": 0.0,
            "peak_since_reset": 0.0, "trading_days_since_reset": set(), "reserve": 0.0,
            "open_positions": [], "switched": False,
        })
    monthly_events = []  # (month_index, funded_pnl, combined_palier)
    start_date = sub["date_creation"].iloc[0]

    for slot_idx in natural_order:
        trade = trades[slot_idx]
        now = slot_arrivals[slot_idx]
        close_time = now + trade["hold_seconds"]
        month_index = int(now // (30.44 * 86400))
        combined_palier = sum(a["palier"] for a in accounts_state)

        for acc in accounts_state:
            acc["open_positions"] = [(t, c) for (t, c) in acc["open_positions"] if c > now]
            if len(acc["open_positions"]) >= MAX_POSITIONS:
                continue
            if any(t in excluded_map[trade["ticker"]] for (t, _) in acc["open_positions"]):
                continue

            current_risk = HIGH_RISK if acc["switched"] else LOW_RISK
            eff_risk, _ = feasible_risk_pct(trade["ticker"], trade["sl_distance"], acc["palier"], current_risk, market_data)
            risk_amount = eff_risk / 100 * acc["palier"]
            pnl = trade["outcome_r"] * risk_amount

            acc["open_positions"].append((trade["ticker"], close_time))
            acc["cumulative_since_reset"] += pnl
            acc["peak_since_reset"] = max(acc["peak_since_reset"], acc["cumulative_since_reset"])
            acc["trading_days_since_reset"].add(int(now // 86400))

            if acc["phase"] == "funded":
                monthly_events.append((month_index, pnl, combined_palier))
                if pnl > 0:
                    acc["reserve"] += pnl * RESERVE_SHARE

            if not acc["switched"] and acc["reserve"] >= RESERVE_SWITCH_THRESHOLD:
                acc["switched"] = True

            dd = acc["peak_since_reset"] - acc["cumulative_since_reset"]
            if dd >= BREAK_DD_PCT / 100 * acc["palier"]:
                cost = CHALLENGE_COST[acc["palier"]]
                if acc["reserve"] >= cost:
                    acc["reserve"] -= cost
                else:
                    acc["reserve"] = 0.0
                acc["phase"] = "challenge"
                acc["cumulative_since_reset"] = 0.0
                acc["peak_since_reset"] = 0.0
                acc["trading_days_since_reset"] = set()
                continue

            if (acc["phase"] == "challenge"
                    and acc["cumulative_since_reset"] >= CHALLENGE_TARGET_PCT / 100 * acc["palier"]
                    and len(acc["trading_days_since_reset"]) >= MIN_TRADING_DAYS):
                acc["phase"] = "funded"
                acc["cumulative_since_reset"] = 0.0
                acc["peak_since_reset"] = 0.0
                acc["trading_days_since_reset"] = set()

            if acc["phase"] == "funded":
                idx = TIER_SEQUENCE.index(acc["palier"])
                if idx + 1 < len(TIER_SEQUENCE):
                    next_tier = TIER_SEQUENCE[idx + 1]
                    cost = UPGRADE_COST[next_tier]
                    if acc["reserve"] >= cost:
                        acc["reserve"] -= cost
                        acc["palier"] = next_tier
                        acc["phase"] = "challenge"
                        acc["cumulative_since_reset"] = 0.0
                        acc["peak_since_reset"] = 0.0
                        acc["trading_days_since_reset"] = set()

    ev_df = pd.DataFrame(monthly_events, columns=["month_index", "pnl", "combined_palier"])
    if not ev_df.empty:
        n_months = ev_df["month_index"].max() + 1
        monthly = ev_df.groupby("month_index").agg(net=("pnl", "sum"), palier_ref=("combined_palier", "last")).reindex(range(n_months))
        monthly["palier_ref"] = monthly["palier_ref"].ffill().bfill()
        monthly["net"] = monthly["net"].fillna(0.0)
        monthly_pct = (monthly["net"] / monthly["palier_ref"] * 100).dropna()
        print(f"Rendement mensuel combiné (%, base = capital combiné courant, profit FINANCÉ seulement) "
              f"sur {len(monthly_pct)} mois avec au moins un mois financé :")
        print(f"  Moyenne    : {monthly_pct.mean():+.2f}%")
        print(f"  Écart-type : {monthly_pct.std():.2f}%")
        print(f"  Médiane    : {monthly_pct.median():+.2f}%")
    else:
        print("Aucun mois en phase financée sur la trajectoire déterministe -- rien à agréger.")

    # === C. Rappel du risque de trésorerie perso en début de vie ===
    print("\n" + "=" * 100)
    print("C. RISQUE DE TRÉSORERIE PERSO EN DÉBUT DE VIE (année 1, réserve~0)")
    print("=" * 100)
    try:
        bb = pd.read_csv("risk_switch_threshold_block_bootstrap_summary.csv")
        row = bb[bb["reserve_threshold"] == 5000.0].iloc[0]
        print(f"[Déjà calculé, block bootstrap {BLOCK_MONTHS} mois, déclencheur réserve>=5000€ -- "
              f"real_cash_paid n'était pas affecté par le bug financé/challenge, réutilisé tel quel]")
        print(f"Trésorerie réelle -- moyenne {row['mean_real_cash']:,.0f}€ | pire cas {row['worst_real_cash']:,.0f}€")
        print(f"P(>1000€) {row['pct_gt_1000']:.2f}% | P(>2000€) {row['pct_gt_2000']:.2f}% | "
              f"P(>3000€) {row['pct_gt_3000']:.2f}%")
    except (FileNotFoundError, IndexError):
        print("[AVERTISSEMENT] risk_switch_threshold_block_bootstrap_summary.csv introuvable.")

    print("\nDétail (2000 runs, profit financé par année) enregistré dans reference_metrics_final_detail.csv")


if __name__ == "__main__":
    main()

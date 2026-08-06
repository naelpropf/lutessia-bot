"""
Budget personnel plafonné et STRICT à 3000€ (pas de rachat possible au-delà, quelle
que soit la suite) : sur les 2000 runs Monte Carlo (block bootstrap 2 mois, année 1,
même construction que year1_loss_decomposition.py) :

1. P(le budget de 3000€ est dépassé pendant l'année 1) -- càd au moins un rachat de
   challenge n'a pas pu être payé faute de réserve suffisante ET de budget perso
   restant, entraînant la retraite définitive d'au moins un des 3 comptes.
2. Parmi ces runs "budget dépassé" : si on avait eu un budget perso illimité (mêmes
   trades, mêmes comptes, aucune retraite forcée), le run aurait-il fini l'année en
   profit net financé positif (occasion manquée) ou serait-il resté en perte de toute
   façon (le plafond n'a coûté qu'une perte déjà actée, pas empêché une reprise) ?

Convention retenue (comme adaptive_risk_test.py) : le plafond de 3000€ est un budget
personnel PARTAGÉ sur les 3 comptes (une seule poche perso), pas 3000€ par compte --
cohérent avec "notre budget personnel". Les upgrades de palier restent, comme partout
ailleurs dans le projet, TOUJOURS gatées par réserve>=coût (jamais de budget perso) :
seul le rachat après casse (BREAK_DD) peut taper dans le budget perso. Dès qu'un rachat
nécessiterait de dépasser le budget perso restant, il n'a PAS lieu : le compte concerné
est retraité définitivement pour le reste du run (mêmes règles que le "hard retirement"
d'adaptive_risk_test.py), et le budget perso déjà engagé reste engagé (coût irrécupérable).
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
from reference_metrics_final import build_full_block_bootstrap_sequence, run_one_hybrid_funded

LOW_RISK = 0.5
HIGH_RISK = 2.0
RESERVE_SWITCH_THRESHOLD = 5000.0
N_ACCOUNTS = 3
YEAR_SECONDS = 365.25 * 86400
BLOCK_MONTHS = 2
PERSONAL_CASH_LIMIT = 3000.0


def run_fleet_year1_capped(trades, slot_arrivals, market_data, excluded_map, order):
    """3 comptes traités EN PARALLÈLE (trade par trade) car ils suivent le même
    signal -- nécessaire ici pour partager une seule poche de budget perso entre eux
    (contrairement aux autres scripts du projet qui traitent chaque compte 'en bloc'
    l'un après l'autre, ce qui serait invalide dès qu'une ressource est partagée dans
    le temps)."""
    accounts = []
    for _ in range(N_ACCOUNTS):
        accounts.append({
            "palier": TIER_SEQUENCE[0], "phase": "challenge", "cumulative_since_reset": 0.0,
            "peak_since_reset": 0.0, "trading_days_since_reset": set(), "reserve": 0.0,
            "open_positions": [], "switched": False, "total_funded_pnl": 0.0,
            "total_fees_paid": CHALLENGE_COST[TIER_SEQUENCE[0]], "retired": False,
        })
    cumulative_personal_cash = 0.0
    budget_exhausted = False

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]

        for acc in accounts:
            if acc["retired"]:
                continue

            close_time = now + trade["hold_seconds"]
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
                acc["total_funded_pnl"] += pnl
                if pnl > 0:
                    acc["reserve"] += pnl * RESERVE_SHARE

            if not acc["switched"] and acc["reserve"] >= RESERVE_SWITCH_THRESHOLD:
                acc["switched"] = True

            drawdown = acc["peak_since_reset"] - acc["cumulative_since_reset"]
            if drawdown >= BREAK_DD_PCT / 100 * acc["palier"]:
                cost = CHALLENGE_COST[acc["palier"]]
                if acc["reserve"] >= cost:
                    acc["reserve"] -= cost
                    acc["total_fees_paid"] += cost
                    acc["phase"] = "challenge"
                    acc["cumulative_since_reset"] = 0.0
                    acc["peak_since_reset"] = 0.0
                    acc["trading_days_since_reset"] = set()
                else:
                    needed_personal = cost - acc["reserve"]
                    if cumulative_personal_cash + needed_personal > PERSONAL_CASH_LIMIT:
                        # budget perso insuffisant pour ce rachat -> retraite définitive
                        acc["retired"] = True
                        budget_exhausted = True
                    else:
                        cumulative_personal_cash += needed_personal
                        acc["reserve"] = 0.0
                        acc["total_fees_paid"] += cost
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
                    cost = UPGRADE_COST[next_tier]  # upgrade : toujours gaté réserve, jamais de budget perso
                    if acc["reserve"] >= cost:
                        acc["reserve"] -= cost
                        acc["total_fees_paid"] += cost
                        acc["palier"] = next_tier
                        acc["phase"] = "challenge"
                        acc["cumulative_since_reset"] = 0.0
                        acc["peak_since_reset"] = 0.0
                        acc["trading_days_since_reset"] = set()

    combined_final_capped = sum(a["total_funded_pnl"] - a["total_fees_paid"] for a in accounts)
    n_retired = sum(1 for a in accounts if a["retired"])
    return combined_final_capped, budget_exhausted, n_retired, cumulative_personal_cash


def run_fleet_year1_uncapped(trades, slot_arrivals, market_data, excluded_map, order):
    combined_final = 0.0
    for _ in range(N_ACCOUNTS):
        _, final_np, _ = run_one_hybrid_funded(trades, slot_arrivals, market_data, excluded_map, order, [YEAR_SECONDS])
        combined_final += final_np
    return combined_final


def main():
    pop = build_population_with_trailing("fixed", 0.2, verbose=False)
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    sub, trades, slot_arrivals = build_trades_trailing(pop)
    tickers = sorted(set(t["ticker"] for t in trades))
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    block_seconds = BLOCK_MONTHS * DAYS_PER_MONTH * 86400
    blocks = build_blocks(trades, slot_arrivals, block_seconds)

    rng = random.Random(42)
    rows = []
    for _ in range(N_SIMULATIONS):
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, YEAR_SECONDS)
        cutoff = sum(1 for s in raw_slots if s <= YEAR_SECONDS)
        synth_trades = raw_trades[:cutoff]
        synth_slots = raw_slots[:cutoff]
        order = list(range(len(synth_trades)))

        capped_final, exhausted, n_retired, cash_used = run_fleet_year1_capped(
            synth_trades, synth_slots, market_data, excluded_map, order
        )
        uncapped_final = run_fleet_year1_uncapped(synth_trades, synth_slots, market_data, excluded_map, order)

        rows.append({
            "capped_final": capped_final, "uncapped_final": uncapped_final,
            "budget_exhausted": exhausted, "n_retired": n_retired, "personal_cash_used": cash_used,
        })

    df = pd.DataFrame(rows)
    df.to_csv("personal_cash_ceiling_detail.csv", index=False)

    n = len(df)
    exhausted = df[df["budget_exhausted"]]
    p_exhausted = len(exhausted) / n * 100

    print("=" * 100)
    print(f"BUDGET PERSO PLAFONNÉ À {PERSONAL_CASH_LIMIT:.0f}€ -- {n} runs, année 1, block bootstrap 2 mois")
    print("=" * 100)
    print(f"P(budget de {PERSONAL_CASH_LIMIT:.0f}€ dépassé pendant l'année 1) = {p_exhausted:.2f}% "
          f"({len(exhausted)}/{n} runs)")

    if not exhausted.empty:
        would_have_recovered = exhausted[exhausted["uncapped_final"] > 0]
        stayed_negative = exhausted[exhausted["uncapped_final"] <= 0]
        p_recover = len(would_have_recovered) / n * 100
        p_stay_negative = len(stayed_negative) / n * 100
        print(f"\nParmi TOUS les {n} runs (probabilités jointes demandées) :")
        print(f"P(budget dépassé ET aurait fini rentable sans plafond) = {p_recover:.2f}% "
              f"({len(would_have_recovered)}/{n})")
        print(f"P(budget dépassé ET serait resté en perte sans plafond) = {p_stay_negative:.2f}% "
              f"({len(stayed_negative)}/{n})")

        print(f"\nParmi les seuls runs 'budget dépassé' (n={len(exhausted)}) :")
        print(f"  -> {len(would_have_recovered)}/{len(exhausted)} "
              f"({len(would_have_recovered)/len(exhausted)*100:.1f}%) auraient fini rentables sans plafond")
        print(f"  -> {len(stayed_negative)}/{len(exhausted)} "
              f"({len(stayed_negative)/len(exhausted)*100:.1f}%) seraient restés en perte de toute façon")
        print(f"\n  Profit net moyen (capped)   sur runs 'budget dépassé'  : {exhausted['capped_final'].mean():+,.0f}€")
        print(f"  Profit net moyen (uncapped) sur runs 'budget dépassé'  : {exhausted['uncapped_final'].mean():+,.0f}€")
        print(f"  Nb moyen de comptes retraités par run 'budget dépassé' : {exhausted['n_retired'].mean():.2f}")

    print(f"\nDétail (2000 runs) enregistré dans personal_cash_ceiling_detail.csv")


if __name__ == "__main__":
    main()

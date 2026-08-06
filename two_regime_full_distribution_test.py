"""
Monte Carlo dédié (nouveau run, pas une relecture de fichiers précédents) : compare
la distribution COMPLÈTE de profit net année 1 entre :
  A. Régime 2% direct, budget personnel "débloqué" (~9-10k€ toujours disponible en
     pratique -- aucune retraite forcée faute de cash dans l'année, cf. le pire cas
     déjà observé à 7992€ dans three_regime_cash_comparison.py, donc un plafond de
     9-10k€ neutralise la contrainte).
  B. Régime hybride verrouillé 0.5%->2%@réserve commune 5000€ (référence).

Même moteur pooled+immunité que three_regime_cash_comparison.py (réserve commune
partagée sur 3 comptes, budget perso jamais retesté après le 1er financement), mais
SANS retraite forcée pour le régime A (puisque le budget est supposé toujours
disponible) -- pas de différence structurelle avec le moteur existant, qui ne
retirait déjà jamais de compte faute de cash (seul personal_cash_ceiling_test.py
imposait une retraite stricte à 3000€). Nouveau tirage indépendant (mêmes graines
42/méthode que d'habitude) pour répondre honnêtement à "dominance stochastique
complète ou pas", pas une déduction des runs déjà faits cette nuit.
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
from reference_metrics_final import build_full_block_bootstrap_sequence

N_ACCOUNTS = 3
YEAR_SECONDS = 365.25 * 86400
BLOCK_MONTHS = 2
RESERVE_SWITCH_THRESHOLD = 5000.0
PERCENTILES = [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95]


def run_fleet_year1(trades, slot_arrivals, market_data, excluded_map, order, low_risk, high_risk, switch_enabled):
    accounts = []
    for _ in range(N_ACCOUNTS):
        accounts.append({
            "palier": TIER_SEQUENCE[0], "phase": "challenge", "cumulative_since_reset": 0.0,
            "peak_since_reset": 0.0, "trading_days_since_reset": set(), "open_positions": [],
            "total_funded_pnl": 0.0, "total_fees_paid": CHALLENGE_COST[TIER_SEQUENCE[0]],
        })
    reserve = 0.0
    switched = False
    ever_funded = False
    real_cash_paid = 0.0

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]

        for acc in accounts:
            close_time = now + trade["hold_seconds"]
            acc["open_positions"] = [(t, c) for (t, c) in acc["open_positions"] if c > now]
            if len(acc["open_positions"]) >= MAX_POSITIONS:
                continue
            if any(t in excluded_map[trade["ticker"]] for (t, _) in acc["open_positions"]):
                continue

            current_risk = (high_risk if switched else low_risk) if switch_enabled else low_risk
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
                    reserve += pnl * RESERVE_SHARE

            if switch_enabled and not switched and reserve >= RESERVE_SWITCH_THRESHOLD:
                switched = True

            drawdown = acc["peak_since_reset"] - acc["cumulative_since_reset"]
            if drawdown >= BREAK_DD_PCT / 100 * acc["palier"]:
                cost = CHALLENGE_COST[acc["palier"]]
                if reserve >= cost:
                    reserve -= cost
                else:
                    shortfall = cost - reserve
                    reserve = 0.0
                    if not ever_funded:
                        real_cash_paid += shortfall  # budget "débloqué" : jamais bloquant, juste comptabilisé
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
                ever_funded = True
                acc["cumulative_since_reset"] = 0.0
                acc["peak_since_reset"] = 0.0
                acc["trading_days_since_reset"] = set()

            if acc["phase"] == "funded":
                idx = TIER_SEQUENCE.index(acc["palier"])
                if idx + 1 < len(TIER_SEQUENCE):
                    next_tier = TIER_SEQUENCE[idx + 1]
                    cost = UPGRADE_COST[next_tier]
                    if reserve >= cost:
                        reserve -= cost
                        acc["total_fees_paid"] += cost
                        acc["palier"] = next_tier
                        acc["phase"] = "challenge"
                        acc["cumulative_since_reset"] = 0.0
                        acc["peak_since_reset"] = 0.0
                        acc["trading_days_since_reset"] = set()

    combined_net = sum(a["total_funded_pnl"] - a["total_fees_paid"] for a in accounts)
    return combined_net, real_cash_paid


def run_regime(blocks, block_seconds, market_data, excluded_map, low_risk, high_risk, switch_enabled, label):
    rng = random.Random(42)
    rows = []
    for _ in range(N_SIMULATIONS):
        raw_trades, raw_slots = build_full_block_bootstrap_sequence(blocks, block_seconds, rng, YEAR_SECONDS)
        cutoff = sum(1 for s in raw_slots if s <= YEAR_SECONDS)
        synth_trades = raw_trades[:cutoff]
        synth_slots = raw_slots[:cutoff]
        order = list(range(len(synth_trades)))

        net, cash = run_fleet_year1(synth_trades, synth_slots, market_data, excluded_map, order, low_risk, high_risk, switch_enabled)
        rows.append({"net_profit": net, "real_cash_paid": cash})

    df = pd.DataFrame(rows)
    df.to_csv(f"two_regime_full_dist_{label}.csv", index=False)
    return df


def main():
    pop = build_population_with_trailing("fixed", 0.2, verbose=False)
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    sub, trades, slot_arrivals = build_trades_trailing(pop)
    tickers = sorted(set(t["ticker"] for t in trades))
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    block_seconds = BLOCK_MONTHS * DAYS_PER_MONTH * 86400
    blocks = build_blocks(trades, slot_arrivals, block_seconds)

    df_2pct = run_regime(blocks, block_seconds, market_data, excluded_map, 2.0, 2.0, False, "2pct_debloque")
    df_hybrid = run_regime(blocks, block_seconds, market_data, excluded_map, 0.5, 2.0, True, "hybride_ref")

    print("=" * 100)
    print("VÉRIFICATION : plafond 9-10k€ neutralise-t-il bien la contrainte ?")
    print("=" * 100)
    print(f"Pire cas trésorerie régime 2% débloqué : {df_2pct['real_cash_paid'].max():,.0f}€ "
          f"({'< 9000€ -> OK, jamais bloquant' if df_2pct['real_cash_paid'].max() < 9000 else 'ATTENTION : dépasse 9000€ !'})")

    print("\n" + "=" * 100)
    print("DISTRIBUTION COMPLÈTE -- PROFIT NET ANNÉE 1 (percentile par percentile)")
    print("=" * 100)
    rows = []
    for p in PERCENTILES:
        v2 = df_2pct["net_profit"].quantile(p)
        vh = df_hybrid["net_profit"].quantile(p)
        better = "2% MEILLEUR" if v2 > vh else ("HYBRIDE MEILLEUR" if vh > v2 else "égalité")
        rows.append({"percentile": f"P{int(p*100)}", "regime_2pct_debloque": v2, "regime_hybride": vh,
                     "diff": v2 - vh, "qui_gagne": better})
    perc_df = pd.DataFrame(rows)
    print(perc_df.to_string(index=False))
    perc_df.to_csv("two_regime_full_dist_percentiles.csv", index=False)

    all_2pct_better = all(r["diff"] >= 0 for r in rows)
    print(f"\nDominance stochastique complète (2% >= hybride à TOUS les percentiles testés) : "
          f"{'OUI' if all_2pct_better else 'NON'}")

    print("\n" + "=" * 100)
    print("VRAIE DISTRIBUTION DE TRÉSORERIE PERSO -- RÉGIME 2% DÉBLOQUÉ (même sans plafond dur)")
    print("=" * 100)
    cash = df_2pct["real_cash_paid"]
    print(f"Moyenne  : {cash.mean():,.0f}€")
    print(f"Médiane  : {cash.median():,.0f}€")
    for p in [0.50, 0.75, 0.90, 0.95, 0.99]:
        print(f"P{int(p*100):<3}     : {cash.quantile(p):,.0f}€")
    print(f"Pire cas : {cash.max():,.0f}€")
    print(f"P(>1000€) {sum(cash>1000)/len(cash)*100:.2f}% | P(>3000€) {sum(cash>3000)/len(cash)*100:.2f}% | "
          f"P(>5000€) {sum(cash>5000)/len(cash)*100:.2f}% | P(>9000€) {sum(cash>9000)/len(cash)*100:.2f}%")

    print("\nRappel régime hybride (référence, budget perso quasi jamais sollicité) :")
    cash_h = df_hybrid["real_cash_paid"]
    print(f"Moyenne  : {cash_h.mean():,.0f}€ | Pire cas : {cash_h.max():,.0f}€")


if __name__ == "__main__":
    main()

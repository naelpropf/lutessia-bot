"""
CORRECTIF (2026-08-01) : run_one() comptait AVANT cette date tout le P&L de trading
(y compris généré en phase "challenge", jamais réellement encaissable) comme profit
réel -- même bug déjà identifié et corrigé le même soir dans sizing_fleet_test.py,
mais jamais propagé ici. Corrigé (total_trading_pnl gaté par phase=="funded"). Tout
CSV/résultat généré via run_one() AVANT cette date (ex. risk_levels_trailing_02_summary.csv,
risk_levels_trailing_summary.csv, risk_levels_realistic_summary.csv et équivalents
copytrade_vs_fleet_*) surestime le profit net de ~30 à 40% (plus l'écart grandit avec
le risque/le nombre de casses) -- à régénérer, ne pas réutiliser tel quel. Voir aussi
le manque de "réserve poolée"/"immunité post-financement" (cf. copytrade_simulation_test.py,
même date) pour la trésorerie perso -- non corrigé dans CE module (run_one reste un
moteur MONO-COMPTE, le pooling se fait au niveau de l'orchestrateur copytrade).

Monte Carlo (bootstrap par permutation) sur la trajectoire de scaling prop firm,
pour connaître la DISTRIBUTION des résultats possibles — pas une seule trajectoire
déterministe comme scaling_simulation.py.

Méthode de rééchantillonnage : les 230 trades réellement capturés (après filtre
plafond 3 positions + corrélation 0.6/JPY, cf. mc_trade_pool.csv) sont mélangés
aléatoirement et réassignés aux 230 CRÉNEAUX D'ARRIVÉE réels de l'historique (mêmes
230 timestamps de départ, dans le même ordre chronologique). Ça préserve le rythme
réel d'arrivée des signaux (nécessaire pour que le filtre plafond/corrélation reste
cohérent) tout en randomisant QUEL trade (ticker, résultat, distance de SL, durée de
détention) tombe à quel moment — teste le risque de séquence : les mêmes trades dans
un ordre différent auraient-ils cassé plus ou moins de comptes, scalé plus ou moins
vite ?

Toutes les règles déjà validées dans scaling_simulation.py sont réutilisées à
l'identique : scaling 50k->200k->500k, +8%/-10% avec 4 jours de trading minimum,
réserve 80% des gains financés, plafond de faisabilité broker (marge + 100 lots),
filtre plafond 3 positions + corrélation 0.6/JPY réappliqué à CHAQUE run (l'ordre
change, donc les trades qui passent le filtre peuvent différer d'un run à l'autre).
"""
import random
import statistics

import pandas as pd

from scaling_simulation import (
    TIER_SEQUENCE, CHALLENGE_COST, UPGRADE_COST, CHALLENGE_TARGET_PCT,
    MIN_TRADING_DAYS, BREAK_DD_PCT, RESERVE_SHARE, MAX_POSITIONS, CORR_THRESHOLD,
    is_jpy, feasible_risk_pct, adaptive_feasible_risk_pct, load_market_data,
    ADAPTIVE_DEFAULT_RISK, ADAPTIVE_FLOOR_RISK,
)

N_SIMULATIONS = 2000
RISK_LEVELS = [1.0, 1.5, 2.0, 3.0, "adaptive"]
POOL_PATH = "mc_trade_pool.csv"


def load_pool_and_slots():
    df = pd.read_csv(POOL_PATH)
    df["date_creation"] = pd.to_datetime(df["date_creation"])
    df["resolution_time_est"] = pd.to_datetime(df["resolution_time_est"])
    df = df.sort_values("date_creation").reset_index(drop=True)

    t0 = df["date_creation"].iloc[0]
    slot_arrivals = [(d - t0).total_seconds() for d in df["date_creation"]]

    trades = []
    for _, row in df.iterrows():
        hold_seconds = (row["resolution_time_est"] - row["date_creation"]).total_seconds()
        sl_distance = abs(row["prix_entree"] - row["stop_loss_init"])
        trades.append({
            "ticker": row["ticker"],
            "outcome_r": row["rr_tp1"] if row["statut_final"] == "OBJECTIF ATTEINT" else -1.0,
            "sl_distance": sl_distance,
            "hold_seconds": hold_seconds,
        })

    return trades, slot_arrivals


def precompute_correlation_pairs(tickers, corr_matrix, threshold):
    """Précalcule, par ticker, l'ensemble des autres tickers avec lesquels il est
    exclu (corrélation ou règle JPY) — évite de relire le DataFrame 2000x par run."""
    excluded = {}
    for a in tickers:
        s = set()
        for b in tickers:
            if a == b:
                continue
            if (is_jpy(a) and is_jpy(b)) or abs(corr_matrix.loc[a, b]) > threshold:
                s.add(b)
        excluded[a] = s
    return excluded


def run_one(trades, slot_arrivals, risk_pct, market_data, excluded_map, rng, order=None):
    """order : permutation pré-calculée à réutiliser (ex: copytrade — le même ordre
    de trades doit être rejoué IDENTIQUE sur plusieurs comptes indépendants, puisque
    c'est le même signal répliqué). Si None (cas normal), une permutation fraîche est
    tirée depuis rng."""
    if order is None:
        order = list(range(len(trades)))
        rng.shuffle(order)

    reserve = 0.0
    palier = TIER_SEQUENCE[0]
    phase = "challenge"
    total_fees_paid = CHALLENGE_COST[palier]
    cumulative_since_reset = 0.0
    peak_since_reset = 0.0
    trading_days_since_reset = set()
    broken_count = 0
    total_trading_pnl = 0.0
    open_positions = []  # (ticker, close_seconds)

    consecutive_breaks = 0
    max_consecutive_breaks = 0
    adaptive_fallback_count = 0

    for slot_idx, trade_idx in enumerate(order):
        trade = trades[trade_idx]
        now = slot_arrivals[slot_idx]
        close_time = now + trade["hold_seconds"]

        open_positions = [(t, c) for (t, c) in open_positions if c > now]

        if len(open_positions) >= MAX_POSITIONS:
            continue
        if any(t in excluded_map[trade["ticker"]] for (t, _) in open_positions):
            continue

        if risk_pct == "adaptive":
            effective_risk_pct, fell_back = adaptive_feasible_risk_pct(
                trade["ticker"], trade["sl_distance"], palier, market_data
            )
            if fell_back:
                adaptive_fallback_count += 1
        else:
            # risk_pct peut être un scalaire (risque fixe) ou une fonction palier->risque
            # (schéma progressif, ex: 0.5% tant qu'on est à 50k, 2% dès 200k+) — le
            # risque cible est réévalué à CHAQUE trade sur le palier COURANT, pas figé
            # au palier de départ.
            target_risk_pct = risk_pct(palier) if callable(risk_pct) else risk_pct
            effective_risk_pct, _ = feasible_risk_pct(
                trade["ticker"], trade["sl_distance"], palier, target_risk_pct, market_data
            )
        risk_amount = effective_risk_pct / 100 * palier
        pnl = trade["outcome_r"] * risk_amount

        open_positions.append((trade["ticker"], close_time))

        if phase == "funded":
            total_trading_pnl += pnl  # CORRECTIF (2026-08-01) : seul le pnl en phase
            # financée est un profit réel -- cf. en-tête du module.
        cumulative_since_reset += pnl
        peak_since_reset = max(peak_since_reset, cumulative_since_reset)
        trading_days_since_reset.add(int(now // 86400))  # jour entier depuis le début

        if phase == "funded" and pnl > 0:
            reserve += pnl * RESERVE_SHARE

        drawdown = peak_since_reset - cumulative_since_reset
        if drawdown >= BREAK_DD_PCT / 100 * palier:
            broken_count += 1
            consecutive_breaks += 1
            max_consecutive_breaks = max(max_consecutive_breaks, consecutive_breaks)
            total_fees_paid += CHALLENGE_COST[palier]
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
            consecutive_breaks = 0  # un palier passé remet le compteur de casses à zéro

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

    net_profit = total_trading_pnl - total_fees_paid
    return {
        "net_profit": net_profit,
        "broken_count": broken_count,
        "final_tier": palier,
        "max_consecutive_breaks": max_consecutive_breaks,
        "adaptive_fallback_count": adaptive_fallback_count,
    }


def run_monte_carlo(risk_pct, trades, slot_arrivals, market_data, excluded_map, n=N_SIMULATIONS, seed=42):
    rng = random.Random(seed)
    results = [run_one(trades, slot_arrivals, risk_pct, market_data, excluded_map, rng) for _ in range(n)]
    return results


def summarize(results):
    profits = sorted(r["net_profit"] for r in results)
    n = len(profits)
    mean_profit = statistics.mean(profits)
    median_profit = statistics.median(profits)
    pct_loss = sum(1 for p in profits if p < 0) / n * 100
    p5 = profits[int(0.05 * n)]
    worst = profits[0]
    best = profits[-1]

    consec = [r["max_consecutive_breaks"] for r in results]
    mean_consec = statistics.mean(consec)
    max_consec = max(consec)

    broken = [r["broken_count"] for r in results]
    mean_broken = statistics.mean(broken)

    fallback = [r["adaptive_fallback_count"] for r in results]
    mean_fallback = statistics.mean(fallback)

    final_tiers = [r["final_tier"] for r in results]
    tier_500k_pct = sum(1 for t in final_tiers if t == 500000) / n * 100
    tier_200k_pct = sum(1 for t in final_tiers if t == 200000) / n * 100
    tier_50k_pct = sum(1 for t in final_tiers if t == 50000) / n * 100

    return {
        "mean_profit": mean_profit, "median_profit": median_profit,
        "pct_loss": pct_loss, "p5_profit": p5, "worst_profit": worst, "best_profit": best,
        "mean_broken_count": mean_broken,
        "mean_max_consecutive_breaks": mean_consec, "max_max_consecutive_breaks": max_consec,
        "pct_final_500k": tier_500k_pct, "pct_final_200k": tier_200k_pct, "pct_final_50k": tier_50k_pct,
        "mean_adaptive_fallback_count": mean_fallback,
    }


def main():
    trades, slot_arrivals = load_pool_and_slots()
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    tickers = sorted(set(t["ticker"] for t in trades))
    excluded_map = precompute_correlation_pairs(tickers, corr_matrix, CORR_THRESHOLD)

    print(f"Pool de trades (rééchantillonné par permutation) : {len(trades)}")
    print(f"Nombre de simulations par niveau de risque : {N_SIMULATIONS}")
    print("⚠️ Bootstrap par permutation : mêmes 230 trades, réassignés aléatoirement aux "
          "230 créneaux d'arrivée réels — teste le risque de séquence, pas la variance "
          "sur un pool de trades différent.\n")

    summary_rows = []
    for risk_pct in RISK_LEVELS:
        results = run_monte_carlo(risk_pct, trades, slot_arrivals, market_data, excluded_map)
        s = summarize(results)
        s["risk_pct"] = risk_pct
        summary_rows.append(s)

        label = f"{risk_pct}%" if isinstance(risk_pct, (int, float)) else \
            f"ADAPTATIF {ADAPTIVE_DEFAULT_RISK}%->{ADAPTIVE_FLOOR_RISK}% (repli si infaisable)"
        print("=" * 100)
        print(f"RISQUE PAR TRADE : {label} — {N_SIMULATIONS} simulations")
        print("=" * 100)
        print(f"Profit net moyen   : {s['mean_profit']:+,.0f}€")
        print(f"Profit net médian  : {s['median_profit']:+,.0f}€")
        print(f"Probabilité de finir en perte nette : {s['pct_loss']:.1f}%")
        print(f"5e percentile (pessimiste réaliste)  : {s['p5_profit']:+,.0f}€")
        print(f"Pire cas observé (2000 runs)         : {s['worst_profit']:+,.0f}€")
        print(f"Meilleur cas observé                 : {s['best_profit']:+,.0f}€")
        print(f"Nombre moyen de casses sur l'horizon  : {s['mean_broken_count']:.2f}")
        print(f"Casses consécutives sans passer de palier — moyenne : {s['mean_max_consecutive_breaks']:.2f}, "
              f"MAX observé sur 2000 runs : {s['max_max_consecutive_breaks']}")
        print(f"Palier final : 500k {s['pct_final_500k']:.1f}% | 200k {s['pct_final_200k']:.1f}% | "
              f"50k {s['pct_final_50k']:.1f}%")
        if risk_pct == "adaptive":
            print(f"Nombre moyen de trades tombés sous le repli 2%->1.5% par run : "
                  f"{s['mean_adaptive_fallback_count']:.2f}")
        print()

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv("monte_carlo_summary.csv", index=False)
    print("Résumé enregistré dans monte_carlo_summary.csv")
    return summary_df


if __name__ == "__main__":
    main()

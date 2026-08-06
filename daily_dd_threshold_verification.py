"""
Vérification du seuil de drawdown utilisé pour déclencher une casse dans le moteur
de simulation (monte_carlo_simulation.py / copytrade_simulation_test.py /
three_firm_fleet_test.py), et quantification de l'écart si une limite JOURNALIÈRE
séparée (3% chez The5%ers) n'est pas modélisée.

CONSTAT CODE (pas d'hypothèse) : les trois scripts importent tous BREAK_DD_PCT=10.0
depuis scaling_simulation.py et l'utilisent de façon identique :
    drawdown = peak_since_reset - cumulative_since_reset
    if drawdown >= BREAK_DD_PCT / 100 * palier: <casse>
C'est un drawdown TRAILING depuis le pic ATTEINT DEPUIS LE DERNIER RESET (challenge
ou financement), PAS une perte journalière calendaire. Aucun des trois scripts (ni
aucun autre fichier .py du projet, grep vérifié) ne contient de logique de perte
journalière (3% chez The5%ers, calculée en EOD sur balance/equity le plus haut).

Donc le "5-6%" évoqué dans la question n'est pas ce qui est codé (c'est 10%), MAIS le
vrai problème est différent et plus grave : la règle journalière séparée à 3% n'est
PAS DU TOUT modélisée, alors qu'elle peut déclencher une casse même quand le
drawdown trailing depuis le pic reste sous 10%.

Ce script rejoue la VRAIE séquence historique (trajectoire déterministe, pas MC) à
100k/2% (repère The5%ers) et compare :
  (a) casses avec SEULEMENT le DD trailing 10% (logique actuelle du code)
  (b) casses avec le DD trailing 10% + une limite journalière 3% ajoutée (agrégat du
      P&L RÉALISÉ des trades qui se CLÔTURENT le même jour calendaire -- proxy, pas
      un vrai mark-to-market intrajournalier des positions ouvertes, qui n'est pas
      trackée par le moteur actuel -- donc ce chiffre est un PLANCHER de l'écart
      réel, pas un plafond).
"""
import pandas as pd

from trailing_payoff_population import build_population_with_trailing, build_trades_trailing
from scaling_simulation import (
    CHALLENGE_TARGET_PCT, MIN_TRADING_DAYS, BREAK_DD_PCT, MAX_POSITIONS, CORR_THRESHOLD,
    feasible_risk_pct, load_market_data, is_jpy,
)

DAILY_LOSS_PCT = 3.0
PALIER = 100000
RISK = 2.0


def run(trades, slot_arrivals, market_data, corr_matrix, with_daily_check):
    phase = "challenge"
    cumulative_since_reset = 0.0
    peak_since_reset = 0.0
    trading_days_since_reset = set()
    open_positions = []
    total_breaks = 0
    breaks_from_daily = 0
    breaks_from_trailing = 0
    daily_pnl = {}

    for idx in range(len(trades)):
        trade = trades[idx]
        now = slot_arrivals[idx]
        close_day = trade["date"].date()

        open_positions = [(t, c) for (t, c) in open_positions if c > now]
        if len(open_positions) >= MAX_POSITIONS:
            continue
        if any((is_jpy(trade["ticker"]) and is_jpy(t)) or abs(corr_matrix.loc[trade["ticker"], t]) > CORR_THRESHOLD
               for (t, _) in open_positions):
            continue

        eff_risk, _ = feasible_risk_pct(trade["ticker"], trade["sl_distance"], PALIER, RISK, market_data)
        risk_amount = eff_risk / 100 * PALIER
        pnl = trade["outcome_r"] * risk_amount

        close_time = now + trade["hold_seconds"]
        open_positions.append((trade["ticker"], close_time))
        cumulative_since_reset += pnl
        peak_since_reset = max(peak_since_reset, cumulative_since_reset)
        trading_days_since_reset.add(int(now // 86400))
        daily_pnl[close_day] = daily_pnl.get(close_day, 0.0) + pnl

        broke = False
        if with_daily_check and daily_pnl[close_day] <= -DAILY_LOSS_PCT / 100 * PALIER:
            broke = True
            breaks_from_daily += 1

        drawdown = peak_since_reset - cumulative_since_reset
        if drawdown >= BREAK_DD_PCT / 100 * PALIER:
            if not broke:
                breaks_from_trailing += 1
            broke = True

        if broke:
            total_breaks += 1
            phase = "challenge"
            cumulative_since_reset = 0.0
            peak_since_reset = 0.0
            trading_days_since_reset = set()
            daily_pnl = {}
            open_positions = []
            continue

        if (phase == "challenge"
                and cumulative_since_reset >= CHALLENGE_TARGET_PCT / 100 * PALIER
                and len(trading_days_since_reset) >= MIN_TRADING_DAYS):
            phase = "funded"
            cumulative_since_reset = 0.0
            peak_since_reset = 0.0
            trading_days_since_reset = set()

    return total_breaks, breaks_from_daily, breaks_from_trailing


def main():
    pop = build_population_with_trailing("fixed", 0.2, verbose=False)
    trades, slot_arrivals = build_trades_trailing(pop)[1:]
    market_data = load_market_data()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)

    tb_10only, _, _ = run(trades, slot_arrivals, market_data, corr_matrix, with_daily_check=False)
    tb_both, from_daily, from_trailing = run(trades, slot_arrivals, market_data, corr_matrix, with_daily_check=True)

    print(f"Trajectoire réelle historique (472 trades), palier {PALIER}$, risque {RISK}%")
    print(f"Casses avec SEULEMENT le DD trailing 10% (logique actuelle du code) : {tb_10only}")
    print(f"Casses avec DD trailing 10% + limite journalière 3% ajoutée        : {tb_both}")
    print(f"  dont déclenchées par la limite journalière 3% (le jour même)     : {from_daily}")
    print(f"  dont déclenchées par le DD trailing 10% (comme avant)            : {from_trailing}")
    if tb_10only:
        print(f"Écart de casses : +{tb_both - tb_10only} ({(tb_both / tb_10only - 1) * 100:+.1f}%)")


if __name__ == "__main__":
    main()

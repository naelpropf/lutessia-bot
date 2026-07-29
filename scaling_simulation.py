"""
Simulation déterministe (PAS un bootstrap Monte Carlo) de trajectoire de compte prop
firm avec scaling, en rejouant la VRAIE séquence chronologique des trades filtrés
(rr_tp1 >= MIN_RR, forex uniquement, 14 paires).

Une seule trajectoire réelle par niveau de risque : "ce qui se serait passé avec cet
historique précis", pas une espérance statistique moyenne sur plusieurs runs.

Règles modélisées (cf. les hypothèses explicitées séparément) :
- Sizing basé sur le palier NOMINAL courant (50k/200k/500k), pas sur une équité qui
  compound en continu — cohérent avec le principe de capital initial fixe déjà
  utilisé dans app_mt5.py (méthode FTMO/The5%ers/Alpha Capital).
- Résultat par trade : +rr_tp1 R si OBJECTIF ATTEINT, -1R si INVALIDÉE (scénario
  "100% TP1", la convention utilisée dans tout le reste de ce projet).
- Plafond de 3 positions simultanées par compte, exclusion par corrélation (|r| >
  CORR_THRESHOLD) avec règle JPY explicite (deux paires JPY toujours exclues entre
  elles, indépendamment du coefficient calculé) — même logique qu'account_router.py.
- Challenge : +8% de gain cumulé ET au moins MIN_TRADING_DAYS jours distincts avec au
  moins un trade pris, sur le palier courant, pour passer financé (les deux
  conditions doivent être réunies — un +8% atteint en 1 jour ne suffit pas).
- Cassure : -10% de drawdown (depuis le pic de la phase courante) sur le palier
  courant -> repaye le challenge de CE palier, repart à zéro sur ce palier.
- Financé : 80% de chaque gain de trade alimente une réserve commune, dédiée
  uniquement au financement des upgrades (200k = 1000€, 500k = 3000€). Dès que la
  réserve suffit, l'upgrade est pris immédiatement.
- Durée d'ouverture d'un trade (pour le filtre plafond/corrélation) : durée réelle
  (résolution vérifiée par les prix H1) quand disponible, sinon durée médiane
  observée sur les trades vérifiés (~7h40), en approximation.
- Faisabilité (cf. position_sizing_feasibility.csv) : si le risque visé nécessite plus
  de marge que le palier courant OU plus de 100 lots (plafond broker), le trade N'EST
  JAMAIS annulé — sa taille (et donc son risque réel) est réduite au maximum
  exécutable, en utilisant les vraies données MT5 par paire (tick_value/tick_size/
  margin_per_lot, snapshot courant — même approximation que pour
  position_sizing_feasibility.csv, pas une marge historique reconstituée).
"""
import itertools
import json

import pandas as pd

from tp_sequence_analysis import FOREX_PATTERN

MARKET_DATA_PATH = "forex_market_data.json"

MIN_RR = 2.0
CORR_THRESHOLD = 0.6
MAX_POSITIONS = 3
CHALLENGE_TARGET_PCT = 8.0
MIN_TRADING_DAYS = 4  # jours distincts avec >=1 trade avant de pouvoir valider un challenge
BREAK_DD_PCT = 10.0
RESERVE_SHARE = 0.80

TIER_SEQUENCE = [50000, 200000, 500000]
CHALLENGE_COST = {50000: 333, 200000: 1000, 500000: 3000}
UPGRADE_COST = {200000: 1000, 500000: 3000}

RISK_LEVELS = [0.5, 1.0, 1.5, 2.0, 3.0]

ADAPTIVE_DEFAULT_RISK = 2.0
ADAPTIVE_FLOOR_RISK = 1.5


def is_jpy(ticker):
    return "JPY" in ticker


def load_population():
    df = pd.read_csv("historique_lutessia_15k.csv")
    df["date_creation"] = pd.to_datetime(df["date_creation"])
    pop = df[(df["rr_tp1"] >= MIN_RR) & (df["statut_final"].isin(["OBJECTIF ATTEINT", "INVALIDÉE"]))].copy()
    pop = pop[pop["ticker"].apply(lambda t: bool(FOREX_PATTERN.match(t)))].copy()

    seq = pd.read_csv("tp_sequence_results_288.csv")
    seq["date_creation"] = pd.to_datetime(seq["date_creation"])
    seq["tp1_time"] = pd.to_datetime(seq["tp1_time"])
    seq["sl_time"] = pd.to_datetime(seq["sl_time"])

    merged = pop.merge(
        seq[["ticker", "date_creation", "tp1_time", "sl_time"]],
        on=["ticker", "date_creation"], how="left",
    )
    merged["resolution_time"] = merged.apply(
        lambda r: r["tp1_time"] if r["statut_final"] == "OBJECTIF ATTEINT" else r["sl_time"], axis=1
    )

    verified = merged[merged["resolution_time"].notna()]
    median_duration = (verified["resolution_time"] - verified["date_creation"]).median()
    merged["resolution_time_est"] = merged["resolution_time"].fillna(merged["date_creation"] + median_duration)
    merged["resolution_verifiee"] = merged["resolution_time"].notna()

    merged = merged.sort_values("date_creation").reset_index(drop=True)
    return merged, median_duration


def correlated(a, b, corr_matrix):
    if is_jpy(a) and is_jpy(b):
        return True
    return abs(corr_matrix.loc[a, b]) > CORR_THRESHOLD


def load_market_data(path=MARKET_DATA_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def feasible_risk_pct(ticker, sl_distance, palier, target_risk_pct, market_data):
    """Réduit (sans jamais annuler) le risque visé au maximum réellement exécutable
    sur ce trade précis : contrainte de marge (< palier) ET plafond broker (100 lots),
    cf. position_sizing_feasibility.csv. Retourne (risque_reel_pct, était_reduit).

    "était_reduit" ne reflète qu'une VRAIE contrainte de capacité (le volume brut
    nécessaire dépasse la marge disponible ou le plafond de 100 lots par plus d'un
    demi-pas de lot) — PAS le simple arrondi au pas de 0.01 lot, qui s'applique à
    presque tous les trades et ne traduit aucune infaisabilité réelle."""
    m = market_data[ticker]
    if sl_distance <= 0:
        return target_risk_pct, False

    loss_per_lot = (sl_distance / m["tick_size"]) * m["tick_value"]
    if loss_per_lot <= 0:
        return target_risk_pct, False

    raw_volume = (target_risk_pct / 100 * palier) / loss_per_lot
    max_volume_margin = palier / m["margin_per_lot"] if m["margin_per_lot"] > 0 else raw_volume
    capped_volume = min(raw_volume, m["volume_max"], max_volume_margin)

    step = m["volume_step"]
    final_volume = max(m["volume_min"], min(m["volume_max"], round(capped_volume / step) * step))

    realized_risk_pct = (final_volume * loss_per_lot) / palier * 100
    was_reduced = capped_volume < raw_volume - step / 2
    return realized_risk_pct, was_reduced


def adaptive_feasible_risk_pct(ticker, sl_distance, palier, market_data):
    """Schéma adaptatif : vise ADAPTIVE_DEFAULT_RISK (2%) par défaut sur chaque trade ;
    si infaisable (marge ou plafond broker 100 lots insuffisant pour ce trade précis),
    retombe sur ADAPTIVE_FLOOR_RISK (1.5%) plutôt que d'annuler le trade. Si même 1.5%
    s'avère infaisable (SL extrêmement large), réduit encore via feasible_risk_pct
    (jamais d'annulation, cohérent avec la règle de faisabilité existante) — ce cas
    résiduel est signalé par le 2e élément du tuple retourné (True = risque réduit
    sous le plancher adaptatif de 1.5%, plutôt qu'un simple repli 2%->1.5%)."""
    realized_default, was_reduced_default = feasible_risk_pct(
        ticker, sl_distance, palier, ADAPTIVE_DEFAULT_RISK, market_data
    )
    if not was_reduced_default:
        return realized_default, False

    realized_floor, was_reduced_floor = feasible_risk_pct(
        ticker, sl_distance, palier, ADAPTIVE_FLOOR_RISK, market_data
    )
    return realized_floor, was_reduced_floor


def run_simulation(pop, corr_matrix, risk_pct, market_data=None):
    reserve = 0.0
    palier = TIER_SEQUENCE[0]
    phase = "challenge"
    total_fees_paid = CHALLENGE_COST[palier]  # coût initial du 1er challenge
    cumulative_since_reset = 0.0
    peak_since_reset = 0.0
    trading_days_since_reset = set()  # jours distincts avec >=1 trade, pour MIN_TRADING_DAYS
    broken_count = 0
    total_trading_pnl = 0.0
    trades_reduced_count = 0
    open_positions = []  # (ticker, close_time)
    monthly_pnl = []  # liste de dicts par trade pris, pour agrégation ensuite
    tier_history = []  # (date, palier) à chaque changement

    start_date = pop["date_creation"].iloc[0]
    tier_history.append((start_date, palier))

    for _, row in pop.iterrows():
        now = row["date_creation"]
        close_time = row["resolution_time_est"]

        open_positions = [(t, c) for (t, c) in open_positions if c > now]

        if len(open_positions) >= MAX_POSITIONS:
            continue
        if any(correlated(row["ticker"], t, corr_matrix) for (t, _) in open_positions):
            continue

        effective_risk_pct = risk_pct
        if market_data is not None:
            sl_distance = abs(row["prix_entree"] - row["stop_loss_init"])
            effective_risk_pct, was_reduced = feasible_risk_pct(
                row["ticker"], sl_distance, palier, risk_pct, market_data
            )
            if was_reduced:
                trades_reduced_count += 1

        risk_amount = effective_risk_pct / 100 * palier
        outcome_r = row["rr_tp1"] if row["statut_final"] == "OBJECTIF ATTEINT" else -1.0
        pnl = outcome_r * risk_amount

        open_positions.append((row["ticker"], close_time))

        total_trading_pnl += pnl
        cumulative_since_reset += pnl
        peak_since_reset = max(peak_since_reset, cumulative_since_reset)
        trading_days_since_reset.add(now.date())

        monthly_pnl.append({"date": now, "pnl": pnl, "palier": palier})

        if phase == "funded" and pnl > 0:
            reserve += pnl * RESERVE_SHARE

        drawdown = peak_since_reset - cumulative_since_reset
        if drawdown >= BREAK_DD_PCT / 100 * palier:
            broken_count += 1
            total_fees_paid += CHALLENGE_COST[palier]
            phase = "challenge"
            cumulative_since_reset = 0.0
            peak_since_reset = 0.0
            trading_days_since_reset = set()
            continue

        # Les deux conditions doivent être réunies : le gain cible peut être atteint
        # bien avant MIN_TRADING_DAYS (et inversement) — le challenge n'est validé
        # qu'au moment où LA DERNIÈRE des deux conditions est remplie.
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
                    tier_history.append((now, palier))

    net_profit = total_trading_pnl - total_fees_paid
    trades_df = pd.DataFrame(monthly_pnl)
    return {
        "risk_pct": risk_pct,
        "broken_count": broken_count,
        "final_tier": palier,
        "total_trading_pnl": total_trading_pnl,
        "total_fees_paid": total_fees_paid,
        "net_profit": net_profit,
        "reserve_finale": reserve,
        "trades_pris": len(trades_df),
        "trades_reduced_count": trades_reduced_count,
        "trades_df": trades_df,
        "tier_history": tier_history,
    }


def build_period_report(trades_df, start_date):
    """Regroupe les trades en blocs de 12 mois glissants depuis start_date : mois 0-11
    = année 1 (rapportée mois par mois), 12-23 = année 2, etc. (rapportées par bloc)."""
    trades_df = trades_df.copy()
    trades_df["month_index"] = trades_df["date"].apply(
        lambda d: (d.year - start_date.year) * 12 + (d.month - start_date.month)
    )

    report = {"year1_months": [], "later_years": []}

    for m in range(12):
        month_trades = trades_df[trades_df["month_index"] == m]
        pnl = month_trades["pnl"].sum()
        palier_ref = month_trades["palier"].iloc[0] if not month_trades.empty else None
        report["year1_months"].append({
            "mois": m + 1,
            "pnl_eur": pnl,
            "palier_ref": palier_ref,
            "pnl_pct": (pnl / palier_ref * 100) if palier_ref else None,
        })

    max_month_index = trades_df["month_index"].max() if not trades_df.empty else 0
    year_num = 2
    m_start = 12
    while m_start <= max_month_index:
        m_end = m_start + 11
        year_trades = trades_df[(trades_df["month_index"] >= m_start) & (trades_df["month_index"] <= m_end)]
        pnl = year_trades["pnl"].sum()
        palier_ref = year_trades["palier"].iloc[0] if not year_trades.empty else None
        report["later_years"].append({
            "annee": year_num,
            "pnl_eur": pnl,
            "palier_ref": palier_ref,
            "pnl_pct": (pnl / palier_ref * 100) if palier_ref else None,
            "mois_couverts": len(year_trades["date"].dt.to_period("M").unique()),
        })
        year_num += 1
        m_start += 12

    return report


def main(apply_feasibility=True, compare=True):
    pop, median_duration = load_population()
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    market_data = load_market_data() if apply_feasibility else None

    print(f"Population forex filtrée (rejouée chronologiquement) : {len(pop)} trades")
    print(f"Période : {pop['date_creation'].min()} -> {pop['date_creation'].max()}")
    print(f"Durée de détention : vérifiée pour {pop['resolution_verifiee'].sum()}/{len(pop)}, "
          f"médiane appliquée en approximation pour le reste : {median_duration}")
    print("\n⚠️ SIMULATION DÉTERMINISTE SUR UNE SEULE TRAJECTOIRE HISTORIQUE RÉELLE — "
          "pas une moyenne statistique sur plusieurs runs. Les résultats montrent ce qui "
          "se serait passé avec CET historique précis, pas une espérance générale.")

    all_results = {}
    comparison_rows = []
    for risk_pct in RISK_LEVELS:
        res = run_simulation(pop, corr_matrix, risk_pct, market_data=market_data)
        report = build_period_report(res["trades_df"], pop["date_creation"].iloc[0])
        all_results[risk_pct] = (res, report)

        res_uncapped = None
        if compare:
            res_uncapped = run_simulation(pop, corr_matrix, risk_pct, market_data=None)
            comparison_rows.append({
                "risk_pct": risk_pct,
                "broken_avec_plafond": res["broken_count"],
                "broken_sans_plafond": res_uncapped["broken_count"],
                "palier_final_avec": res["final_tier"],
                "palier_final_sans": res_uncapped["final_tier"],
                "net_profit_avec": res["net_profit"],
                "net_profit_sans": res_uncapped["net_profit"],
                "ecart_eur": res["net_profit"] - res_uncapped["net_profit"],
                "trades_reduits": res["trades_reduced_count"],
            })

        print("\n" + "=" * 100)
        print(f"RISQUE PAR TRADE : {risk_pct}%")
        print("=" * 100)
        print(f"Trades pris (après filtre plafond/corrélation) : {res['trades_pris']} / {len(pop)}")
        if market_data is not None:
            print(f"Dont trades réduits par la contrainte de faisabilité (marge/100 lots) : {res['trades_reduced_count']}")
        print(f"Comptes cassés sur toute la période : {res['broken_count']}")
        print(f"Palier atteint en fin de période : {res['final_tier']}€")
        print(f"Historique des upgrades : {res['tier_history']}")
        print(f"Profit brut de trading (avant frais) : {res['total_trading_pnl']:+,.0f}€")
        print(f"Frais de challenge/recasse/upgrade payés au total : {res['total_fees_paid']:,.0f}€")
        print(f"PROFIT NET TOTAL : {res['net_profit']:+,.0f}€")

        print(f"\n--- Année 1, mois par mois (palier de référence pour le %) ---")
        for m in report["year1_months"]:
            pct_str = f"{m['pnl_pct']:+.2f}%" if m["pnl_pct"] is not None else "n/a"
            print(f"  Mois {m['mois']:>2} : {m['pnl_eur']:+10,.0f}€ ({pct_str}, palier {m['palier_ref']})")

        print(f"\n--- Années suivantes ---")
        if not report["later_years"]:
            print("  (historique insuffisant pour une 2e année complète)")
        for y in report["later_years"]:
            pct_str = f"{y['pnl_pct']:+.2f}%" if y["pnl_pct"] is not None else "n/a"
            print(f"  Année {y['annee']} ({y['mois_couverts']} mois couverts) : "
                  f"{y['pnl_eur']:+10,.0f}€ ({pct_str}, palier {y['palier_ref']})")

    if compare and comparison_rows:
        comp_df = pd.DataFrame(comparison_rows)
        comp_df.to_csv("scaling_simulation_feasibility_comparison.csv", index=False)
        print("\n" + "=" * 100)
        print("TABLEAU COMPARATIF FINAL — avec vs sans plafond de faisabilité")
        print("=" * 100)
        print(comp_df.to_string(index=False))

    return all_results


if __name__ == "__main__":
    main()

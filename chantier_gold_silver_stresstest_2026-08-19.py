"""Stress-test H1/H2 + 4 blocs k-fold, configs routage metaux A/B (2026-08-19).
Meme protocole que le reste du projet (chantier_stresstest_pisteAB_2026-08-
19.py:727-732) -- population source restreinte au sous-ensemble chronologique
AVANT le block-bootstrap, n reduit pour rester raisonnable.

Sous-periodes appliquees INDEPENDAMMENT a A et B (chacune tronquee a sa
propre fraction chronologique -- A et B n'ont pas exactement le meme
historique, mais la meme fraction relative de chaque flux).

Verification demandee (Config 2, "point de vigilance") : correlation entre
le P&L de compte A et le P&L de compte B, par simulation -- si Config 2
(overflow) montre une correlation A/B significativement plus elevee que
Config 0 (aucune interaction A/B au-dela de la reserve commune, deja
partagee dans TOUTES les configs), ce serait le signe d'un risque partage
NOUVEAU introduit par l'overflow (au-dela du mecanisme de reserve commune
deja connu, cf. chantier_ab_parallele_2026-08-19.py:13-21).
"""
import importlib.util
import time

import numpy as np
import pandas as pd

_spec = importlib.util.spec_from_file_location("gsengine", "chantier_gold_silver_ab_engine_2026-08-19.py")
gse = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gse)


def run_one_joint_with_accounts(fmt_A, fmt_B, blocks_A, blocks_B, market_data, excluded_map, rng, horizon_seconds,
                                 cost_A, cost_B, config, metal_ticker_set):
    """Copie de gse.run_one_joint, AJOUTE le P&L final PAR COMPTE (pas juste le
    profit_net combine) -- necessaire pour le point de vigilance Config 2."""
    (trA, slA), (trB, slB) = gse.build_joint_bootstrap_sequence(blocks_A, blocks_B, gse.BLOCK_SECONDS, rng, horizon_seconds)
    from engine_multiformat import make_acc_mf
    accA = make_acc_mf(fmt_A, gse.PALIER, cost_A)
    accB = make_acc_mf(fmt_B, gse.PALIER, cost_B)
    state = {"reserve": 0.0, "total_breaks": 0, "real_cash_paid": cost_A + cost_B, "overflow_to_A": 0}

    events = [(t, "A", tr) for tr, t in zip(trA, slA)] + [(t, "B", tr) for tr, t in zip(trB, slB)]
    events.sort(key=lambda e: e[0])

    for now, which, trade in events:
        if config == "2" and which == "B" and trade["ticker"] in metal_ticker_set:
            gse.route_metal_config2(accA, accB, trade, now, fmt_A, fmt_B, state, market_data, excluded_map)
        else:
            acc = accA if which == "A" else accB
            fmt = fmt_A if which == "A" else fmt_B
            gse.process_trade_corr_swap_rr(acc, trade, now, fmt, state, gse.trade_risk(acc), market_data, excluded_map,
                                            split_flat=gse.SPLIT_FLAT, reserve_share=gse.RESERVE_SHARE,
                                            routing_field=gse.ROUTING_FIELD)

    return dict(pnl_A=accA["total_funded_pnl"], pnl_B=accB["total_funded_pnl"],
                profit_net=accA["total_funded_pnl"] + accB["total_funded_pnl"] - state["real_cash_paid"])


def load_config_pops(config):
    if config == "baseline":
        pop_A = pd.read_csv("chantier_gold_silver_pop_A_config0_2026-08-19.csv")
        pop_B = pd.read_csv("chantier_gold_silver_pop_B_config0_2026-08-19.csv")
        pop_B = pop_B[~pop_B["ticker"].str.match(r"^(GOLD|SILVER) - ")].reset_index(drop=True)
        metal_set = set()
    elif config == "0":
        pop_A = pd.read_csv("chantier_gold_silver_pop_A_config0_2026-08-19.csv")
        pop_B = pd.read_csv("chantier_gold_silver_pop_B_config0_2026-08-19.csv")
        metal_set = set()
    elif config == "1":
        pop_A = pd.read_csv("chantier_gold_silver_pop_A_config1_2026-08-19.csv")
        pop_B = pd.read_csv("chantier_gold_silver_pop_B_config1_2026-08-19.csv")
        metal_set = set()
    elif config == "2":
        pop_A = pd.read_csv("chantier_gold_silver_pop_A_config0_2026-08-19.csv")
        pop_B = pd.read_csv("chantier_gold_silver_pop_B_config0_2026-08-19.csv")
        oa = pd.read_csv("chantier_gold_silver_pop_metaux_all_2026-08-19.csv")
        metal_set = set(oa["ticker"].unique())
    else:
        raise ValueError(config)
    for df in (pop_A, pop_B):
        df["date_creation"] = pd.to_datetime(df["date_creation"])
        df["resolution_time_est"] = pd.to_datetime(df["resolution_time_est"])
    return pop_A, pop_B, metal_set


def subperiod_split(pop, n_parts):
    pop = pop.sort_values("date_creation").reset_index(drop=True)
    parts = np.array_split(pop, n_parts)
    return [p.reset_index(drop=True) for p in parts]


def run_subperiod(pop_A_sub, pop_B_sub, metal_set, config, n_sims, seed=9999):
    trades_A, dates_A = gse.df_to_trades(pop_A_sub)
    trades_B, dates_B = gse.df_to_trades(pop_B_sub)
    if len(trades_A) == 0 or len(trades_B) == 0:
        return None
    anchor = min(dates_A.min(), dates_B.min())
    slots_A = [(d - anchor).total_seconds() for d in dates_A]
    slots_B = [(d - anchor).total_seconds() for d in dates_B]
    horizon_seconds = max(slots_A[-1], slots_B[-1])
    n_blocks = int(horizon_seconds // gse.BLOCK_SECONDS) + 1
    if n_blocks < 2:
        return None

    blocks_A = gse.build_aligned_blocks(trades_A, slots_A, gse.BLOCK_SECONDS, n_blocks)
    blocks_B = gse.build_aligned_blocks(trades_B, slots_B, gse.BLOCK_SECONDS, n_blocks)

    market_data = gse.load_common()
    all_tickers = sorted(set(t["ticker"] for t in trades_A) | set(t["ticker"] for t in trades_B))
    corr_matrix = pd.read_csv("correlation_matrix.csv", index_col=0)
    from monte_carlo_simulation import precompute_correlation_pairs
    from scaling_simulation import CORR_THRESHOLD
    excluded_map = precompute_correlation_pairs(all_tickers, corr_matrix, CORR_THRESHOLD)

    from engine_multiformat import FORMATS
    fmt = FORMATS["Blueberry_InstantElite"]
    cost = fmt["price"][gse.PALIER]

    rng = np.random.RandomState(seed)
    import random
    rrng = random.Random(seed)
    rows = [run_one_joint_with_accounts(fmt, fmt, blocks_A, blocks_B, market_data, excluded_map, rrng,
                                         horizon_seconds, cost, cost, config, metal_set) for _ in range(n_sims)]
    profits = np.array([r["profit_net"] for r in rows])
    pnl_A = np.array([r["pnl_A"] for r in rows])
    pnl_B = np.array([r["pnl_B"] for r in rows])
    corr_AB = np.corrcoef(pnl_A, pnl_B)[0, 1] if np.std(pnl_A) > 0 and np.std(pnl_B) > 0 else float("nan")
    return dict(n=n_sims, profit_moyen=profits.mean(), corr_A_B=corr_AB)


def main():
    import sys
    n_sims = int(sys.argv[1]) if len(sys.argv) > 1 else 50

    configs = ["baseline", "0", "1", "2"]
    all_rows = []
    t0 = time.time()
    for config in configs:
        pop_A, pop_B, metal_set = load_config_pops(config)
        subA = {"H1": subperiod_split(pop_A, 2)[0], "H2": subperiod_split(pop_A, 2)[1]}
        for i, p in enumerate(subperiod_split(pop_A, 4)):
            subA[f"bloc{i}"] = p
        subB = {"H1": subperiod_split(pop_B, 2)[0], "H2": subperiod_split(pop_B, 2)[1]}
        for i, p in enumerate(subperiod_split(pop_B, 4)):
            subB[f"bloc{i}"] = p

        print(f"\n{'='*70}\nConfig {config}\n{'='*70}")
        for sp_name in subA:
            t1 = time.time()
            res = run_subperiod(subA[sp_name], subB[sp_name], metal_set, config, n_sims)
            if res is None:
                print(f"  [{sp_name}] insuffisant (trop peu de trades/blocs), ignore")
                continue
            print(f"  [{sp_name}, n={n_sims}] profit_moy={res['profit_moyen']:+,.0f}$ "
                  f"corr(pnl_A,pnl_B)={res['corr_A_B']:+.3f} ({time.time()-t1:.0f}s)")
            all_rows.append(dict(config=config, subperiod=sp_name, **res))
            pd.DataFrame(all_rows).to_csv("chantier_gold_silver_stresstest_2026-08-19.csv", index=False)

    print(f"\nTermine en {time.time()-t0:.0f}s.")


if __name__ == "__main__":
    main()

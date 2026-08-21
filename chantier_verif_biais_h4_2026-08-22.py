"""chantier_verif_biais_h4_2026-08-22.py

Point D, volet C (demande utilisateur 22/08) : quantifier empiriquement le
biais introduit par l'usage de bougies H4 (au lieu de H1) pour Palladium
2021-03->2023-01 et le residu FX legs 2021-03->2022-01. Methode : pour les
trades PALLADIUM ayant de VRAIES bougies H1 (post 2023-01-19, backfill MT5
natif, aucune substitution), on calcule r_trailing 2 fois -- (a) avec les
vraies bougies H1 (deja la reference utilisee partout ailleurs dans le
projet), (b) avec ces MEMES bougies H1 regroupees en H4 synthetique (open du
1er sous-bar, high=max, low=min, close du dernier) -- exactement ce que
produirait TradingView en H4 sur la meme donnee sous-jacente. La comparaison
(b) vs (a) isole le seul effet de la RESOLUTION, sans aucune autre variable
confondue (meme source de prix, memes trades)."""
import importlib.util

import pandas as pd

_spec = importlib.util.spec_from_file_location("tpseq", "tp_sequence_analysis.py")
tpseq = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tpseq)

_spec_tsv = importlib.util.spec_from_file_location("tsv", "trailing_stop_variants.py")
tsv = importlib.util.module_from_spec(_spec_tsv)
_spec_tsv.loader.exec_module(tsv)

TRAILING_FACTOR_METAUX = 0.10


def _stop_fn(param):
    def fn(extreme, entry, risk_distance, atr):
        is_long_direction = extreme >= entry
        return extreme - param * risk_distance if is_long_direction else extreme + param * risk_distance
    return fn


def h1_to_synthetic_h4(h1):
    """Regroupe des bougies H1 en H4 synthetique, alignees sur les frontieres
    00/04/08/12/16/20h UTC (meme convention que les vraies bougies H4
    TradingView, verifie visuellement sur l'export xpdusd_h4_export)."""
    h1 = h1.copy().sort_values("datetime").reset_index(drop=True)
    h1["h4_bucket"] = h1["datetime"].dt.floor("4H")
    agg = h1.groupby("h4_bucket").agg(
        open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"),
    ).reset_index().rename(columns={"h4_bucket": "datetime"})
    return agg


def main():
    pop = pd.read_csv("chantier_gold_silver_pop_B_tradable_pgp_2026-08-20.csv")
    pop["date_creation"] = pd.to_datetime(pop["date_creation"])

    pdpt_raw = pd.read_csv("historique_gaz_palladium_platine_pilote_2026-08-20.csv")
    pdpt_raw["date_creation"] = pd.to_datetime(pdpt_raw["date_creation"])
    pop = pop.merge(pdpt_raw[["date_creation", "ticker", "tp1_init", "tp2_init"]],
                     on=["date_creation", "ticker"], how="left")

    pd_trades = pop[(pop["ticker"] == "PALLADIUM") & (pop["r_trailing"] > 0)
                     & (pop["date_creation"] >= "2023-02-01")].reset_index(drop=True)
    print(f"Trades PALLADIUM gagnants avec vraies bougies H1 natives (>=2023-02-01) : {len(pd_trades)}")

    h1_full = pd.read_csv("data/mt5_h1_backfill/mt5_h1_backfill_XPDUSD.pi_2026-08-21.csv",
                           usecols=["datetime", "open", "high", "low", "close"])
    h1_full["datetime"] = pd.to_datetime(h1_full["datetime"])
    h4_synth = h1_to_synthetic_h4(h1_full)

    rows = []
    for _, row in pd_trades.iterrows():
        res_h1 = tpseq.analyze_trade(row, h1_full)
        res_h4 = tpseq.analyze_trade(row, h4_synth)

        def resolve_r(res, candles):
            case = res.get("case", "pas_de_donnees")
            if case in {"tp1_avant_tp2", "meme_bougie"}:
                sim = tsv.simulate_trailing(row, candles, _stop_fn(TRAILING_FACTOR_METAUX), "fixed_0.10")
                return sim["exit_r"] if sim is not None else row["rr_tp1"], case
            return row["rr_tp1"], case

        r_h1, case_h1 = resolve_r(res_h1, h1_full)
        r_h4, case_h4 = resolve_r(res_h4, h4_synth)
        rows.append(dict(date_creation=row["date_creation"], r_trailing_original=row["r_trailing"],
                          r_h1_recalc=r_h1, r_h4_synth=r_h4, case_h1=case_h1, case_h4=case_h4))

    out = pd.DataFrame(rows)
    out.to_csv("chantier_verif_biais_h4_detail_2026-08-22.csv", index=False)

    out["delta_h4_moins_h1"] = out["r_h4_synth"] - out["r_h1_recalc"]
    print(f"\nn={len(out)}")
    print(f"EV H1 (reference)      : {out['r_h1_recalc'].mean():+.4f}R")
    print(f"EV H4 synthetique      : {out['r_h4_synth'].mean():+.4f}R")
    print(f"Delta moyen (H4-H1)    : {out['delta_h4_moins_h1'].mean():+.4f}R")
    print(f"Delta median (H4-H1)   : {out['delta_h4_moins_h1'].median():+.4f}R")
    print(f"Delta abs moyen        : {out['delta_h4_moins_h1'].abs().mean():.4f}R")
    print(f"% trades ou H4 < H1    : {(out['delta_h4_moins_h1'] < -1e-9).mean()*100:.1f}%")
    print(f"% trades ou H4 > H1    : {(out['delta_h4_moins_h1'] > 1e-9).mean()*100:.1f}%")
    print(f"% trades identiques    : {(out['delta_h4_moins_h1'].abs() <= 1e-9).mean()*100:.1f}%")
    print(f"\nRepartition case_h1 : {out['case_h1'].value_counts().to_dict()}")
    print(f"Repartition case_h4 : {out['case_h4'].value_counts().to_dict()}")


if __name__ == "__main__":
    main()

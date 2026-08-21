"""chantier_piste2_confluence_multihorizon_2026-08-21.py

Piste 2 (confluence multi-horizons) -- premier passage exploratoire
(screening, PAS un resultat a adopter), demande utilisateur session du
21/08. Objectif : verifier si un filtre de confluence multi-horizons
(pente EMA + signe MACD, 2 horizons calibres sur la distribution de duree
de vie des trades B) change les stats de bloc2 (fenetre 2022-08-20 ->
2023-12-17, regime "chop" deja diagnostique).

Etape 0 (deja faite, session du 21/08) : distribution de duree de vie sur
B_tradable+Pd/Pt (n=1248) -- mediane=8,63h, p25=7,48h, p75=12,74h,
p90=41,26h, tres concentree (88,1% <24h).

Etape 1 (deja faite) : horizons retenus = 8 bougies H1 (court, proche
mediane) et 40 bougies H1 (long, x5, proche p90) -- decision utilisateur :
ces horizons servent DIRECTEMENT de PERIODE pour l'EMA (pas de convention
Lutessia externe a matcher, introuvable dans le code -- Lutessia est un
fournisseur de signaux externe).

Population testee : 571 forex/indices de B_tradable (chantier_gold_silver_
pop_B_config0_tradable_2026-08-19.csv, metaux exclus) -- decision
utilisateur : PAS B_tradable+Pd/Pt (n=1248), le diagnostic bloc2 (chop) est
specifique forex/indices (raison pour laquelle ADX-fx-only exclut deja les
metaux). Reference bloc2 recalculee fraichement sur r_trailing (deja
corrige du trailing stop), PAS les chiffres externes non retracables
(42,12%/+0,0135R/p=0,0025).

Bougies H1 : source MT5 backfill (data/mt5_h1_backfill/, pull du VPS le
21/08, commit ebfa299) -- couvre 2022-01-02->2026-08-20 pour tout le forex
(0 gap>4j) et les indices en CFD continu (GER30.p/GER40.p pour DAX,
SP500.p, NAS100.p -- PAS les futures FULL0926 exacts, absents du compte
MT5 source). Alignement horaire verifie contre le cache yfinance existant
(meme heure UTC a la bougie pres) avant utilisation.

Interpretation retenue pour "horizon" applique au MACD(12,26,9), standard
a parametres FIXES (contrairement a l'EMA dont le "horizon" EST la
periode) : MACD calcule sur les `horizon` dernieres bougies H1 avant
l'entree (fenetre glissante tronquee, PAS l'historique complet) -- seule
lecture qui rend le signal reellement horizon-dependant. CAVEAT explicite :
a horizon=8, la fenetre est plus courte que la periode lente du MACD
(26) -- signal immature/instable, a interpreter avec prudence, pas comme
un MACD(12,26,9) pleinement converge.
"""
import numpy as np
import pandas as pd
from scipy import stats as sps

MT5_DIR = "data/mt5_h1_backfill"
HORIZON_SHORT = 8
HORIZON_LONG = 40

# ticker Lutessia -> fichier(s) MT5 backfill (liste = a concatener, ex. DAX40 GER30->GER40)
TICKER_TO_MT5_FILES = {
    "AUD/JPY": ["AUDJPY.pi"], "AUD/USD": ["AUDUSD.pi"], "CHF/JPY": ["CHFJPY.pi"],
    "EUR/CHF": ["EURCHF.pi"], "EUR/GBP": ["EURGBP.pi"], "EUR/JPY": ["EURJPY.pi"],
    "EUR/USD": ["EURUSD.pi"], "GBP/CHF": ["GBPCHF.pi"], "GBP/JPY": ["GBPJPY.pi"],
    "GBP/USD": ["GBPUSD.pi"], "NZD/USD": ["NZDUSD.pi"], "USD/CAD": ["USDCAD.pi"],
    "USD/CHF": ["USDCHF.pi"], "USD/JPY": ["USDJPY.pi"],
    "DAX40 FULL0926": ["GER30.p", "GER40.p"], "DAX40 PERF INDEX": ["GER30.p", "GER40.p"],
    "NASDAQ100 - MINI NASDAQ100 FULL0926": ["NAS100.p"], "NASDAQ100 INDEX": ["NAS100.p"],
    "S&P500 - MINI S&P500 FULL0926": ["SP500.p"],
}

BLOC_EDGES = pd.to_datetime([
    "2021-04-23 12:43:32", "2022-08-20 17:22:34.250",
    "2023-12-17 22:01:36.500", "2025-04-15 02:40:38.750", "2026-08-12 07:19:41",
])


def load_population():
    # MAJ 2026-08-22 : source remplacee par la population B corrigee (fix
    # r_trailing df261dc + backfill metaux complet + regen forex/indices,
    # cf. session_handoff_2026-08-22.md). L'ancien fichier config0_tradable
    # (2026-08-19/20) predatait ces deux corrections -- c'est la donnee
    # "incomplete" sur laquelle piste 2 avait ete rejetee la premiere fois.
    pop = pd.read_csv("chantier_gold_silver_pop_B_tradable_pgp_2026-08-20.csv")
    pop["date_creation"] = pd.to_datetime(pop["date_creation"])
    metal_kw = ["GOLD", "SILVER", "PALLADIUM", "PLATINUM"]
    is_metal = pop["ticker"].str.contains("|".join(metal_kw), case=False, na=False)
    pop = pop[~is_metal].reset_index(drop=True)
    assert len(pop) == 571, f"n inattendu : {len(pop)} (attendu 571)"
    pop["direction"] = np.where(pop["stop_loss_init"] < pop["prix_entree"], "achat", "vente")
    bloc = pd.cut(pop["date_creation"], bins=BLOC_EDGES, labels=["bloc1", "bloc2", "bloc3", "bloc4"])
    pop["bloc"] = bloc.astype(str)
    return pop


_candle_cache = {}


def load_candles(ticker):
    if ticker in _candle_cache:
        return _candle_cache[ticker]
    files = TICKER_TO_MT5_FILES[ticker]
    dfs = []
    for f in files:
        path = f"{MT5_DIR}/mt5_h1_backfill_{f}_2026-08-21.csv"
        d = pd.read_csv(path, usecols=["datetime", "open", "high", "low", "close"])
        d["datetime"] = pd.to_datetime(d["datetime"])
        dfs.append(d)
    c = pd.concat(dfs, ignore_index=True).drop_duplicates(subset="datetime").sort_values("datetime").reset_index(drop=True)
    c["ema_short"] = c["close"].ewm(span=HORIZON_SHORT, adjust=False).mean()
    c["ema_long"] = c["close"].ewm(span=HORIZON_LONG, adjust=False).mean()
    _candle_cache[ticker] = c
    return c


def macd_sign_windowed(closes, horizon):
    """MACD(12,26,9) calcule sur les `horizon` dernieres bougies (fenetre
    tronquee, cf. docstring module) -- signe de (macd_line - signal_line)
    au dernier point."""
    window = closes.tail(horizon)
    if len(window) < 2:
        return "neutre"
    ema12 = window.ewm(span=12, adjust=False).mean()
    ema26 = window.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    hist = (macd_line - signal_line).iloc[-1]
    if hist > 0:
        return "achat"
    if hist < 0:
        return "vente"
    return "neutre"


def ema_slope_sign(ema_series):
    if len(ema_series) < 2:
        return "neutre"
    d = ema_series.iloc[-1] - ema_series.iloc[-2]
    if d > 0:
        return "achat"
    if d < 0:
        return "vente"
    return "neutre"


def compute_signals(pop):
    sig_ema_short, sig_ema_long, sig_macd_short, sig_macd_long = [], [], [], []
    n_no_candles = 0
    for _, row in pop.iterrows():
        c = load_candles(row["ticker"])
        prior = c[c["datetime"] <= row["date_creation"]]
        if len(prior) < HORIZON_LONG + 2:
            sig_ema_short.append(None); sig_ema_long.append(None)
            sig_macd_short.append(None); sig_macd_long.append(None)
            n_no_candles += 1
            continue
        sig_ema_short.append(ema_slope_sign(prior["ema_short"].tail(2)))
        sig_ema_long.append(ema_slope_sign(prior["ema_long"].tail(2)))
        sig_macd_short.append(macd_sign_windowed(prior["close"], HORIZON_SHORT))
        sig_macd_long.append(macd_sign_windowed(prior["close"], HORIZON_LONG))
    pop = pop.copy()
    pop["sig_ema_short"] = sig_ema_short
    pop["sig_ema_long"] = sig_ema_long
    pop["sig_macd_short"] = sig_macd_short
    pop["sig_macd_long"] = sig_macd_long
    print(f"[compute_signals] {n_no_candles}/{len(pop)} trades sans historique suffisant (< {HORIZON_LONG+2} bougies avant entree) -- signaux=None")
    return pop


SIGNAL_COLS = ["sig_ema_short", "sig_ema_long", "sig_macd_short", "sig_macd_long"]


def confluence_count(pop):
    def count_row(row):
        if any(row[c] is None for c in SIGNAL_COLS):
            return None
        return sum(1 for c in SIGNAL_COLS if row[c] == row["direction"])
    pop = pop.copy()
    pop["confluence_n"] = pop.apply(count_row, axis=1)
    return pop


def stats_block(df, label):
    n = len(df)
    if n == 0:
        return dict(label=label, n=0, wins=0, losses=0, winrate=float("nan"), ev=float("nan"), se=float("nan"))
    wins = int((df["r_trailing"] > 0).sum())
    losses = int((df["r_trailing"] <= 0).sum())
    ev = df["r_trailing"].mean()
    se = df["r_trailing"].std(ddof=1) / np.sqrt(n) if n > 1 else float("nan")
    return dict(label=label, n=n, wins=wins, losses=losses, winrate=wins / n * 100, ev=ev, se=se)


def print_stats(d):
    print(f"  {d['label']:28s} n={d['n']:4d} wins={d['wins']:4d} losses={d['losses']:4d} "
          f"winrate={d['winrate']:6.2f}% EV={d['ev']:+.4f}R se={d['se']:.4f}")


def main():
    pop = load_population()
    print(f"Population totale (571) chargee, repartition blocs :")
    print(pop["bloc"].value_counts())
    print()

    pop = compute_signals(pop)
    pop = confluence_count(pop)
    pop.to_csv("chantier_piste2_signaux_2026-08-21.csv", index=False)

    valid = pop.dropna(subset=["confluence_n"])
    print(f"\n{len(valid)}/{len(pop)} trades avec signaux calculables (historique H1 suffisant).")

    # ================= ETAPE 4 : bloc2 =================
    print(f"\n{'='*90}\nETAPE 4 -- bloc2 (reference fraiche + filtres confluence)\n{'='*90}")
    b2 = valid[valid["bloc"] == "bloc2"]
    b2_all_raw = pop[pop["bloc"] == "bloc2"]
    ref = stats_block(b2_all_raw, "bloc2 REFERENCE (571, brut)")
    print_stats(ref)
    ref_valid = stats_block(b2, "bloc2 reference (signaux calculables)")
    print_stats(ref_valid)

    for th in (2, 3, 4):
        kept = b2[b2["confluence_n"] >= th]
        excl = b2[b2["confluence_n"] < th]
        s_kept = stats_block(kept, f"bloc2 confluence>={th}/4 KEPT")
        s_excl = stats_block(excl, f"bloc2 confluence>={th}/4 EXCLUDED")
        print_stats(s_kept)
        print_stats(s_excl)
        if len(kept) > 1 and len(excl) > 1:
            t, p = sps.ttest_ind(kept["r_trailing"], excl["r_trailing"], equal_var=False)
            print(f"    Welch t-test EV kept vs excluded : t={t:.3f} p={p:.4f}")
        if len(kept) > 1 and len(b2_all_raw) > 1:
            t2, p2 = sps.ttest_ind(kept["r_trailing"], b2_all_raw["r_trailing"], equal_var=False)
            print(f"    Welch t-test EV kept vs bloc2 baseline (brut) : t={t2:.3f} p={p2:.4f}")
        print()

    # ================= ETAPE 5 : controle bloc1/bloc3/bloc4 =================
    print(f"\n{'='*90}\nETAPE 5 -- controle bloc1/bloc3/bloc4 (meme regle, seuil 3/4)\n{'='*90}")
    for bl in ("bloc1", "bloc3", "bloc4"):
        sub_all = pop[pop["bloc"] == bl]
        sub_valid = valid[valid["bloc"] == bl]
        base = stats_block(sub_all, f"{bl} baseline (571, brut)")
        print_stats(base)
        for th in (2, 3, 4):
            kept = sub_valid[sub_valid["confluence_n"] >= th]
            pct_filtered = 100 * (1 - len(kept) / len(sub_valid)) if len(sub_valid) else float("nan")
            s_kept = stats_block(kept, f"{bl} confluence>={th}/4 KEPT ({pct_filtered:.1f}% filtres)")
            print_stats(s_kept)
        print()

    # ================= ETAPE 6 (bonus) : desaccord court/long dans les exclus bloc2 =================
    print(f"\n{'='*90}\nETAPE 6 (bonus) -- desaccord EMA court/long, trades EXCLUS de bloc2 (seuil 3/4)\n{'='*90}")
    excl3 = b2[b2["confluence_n"] < 3]
    disagree = excl3[excl3["sig_ema_short"] != excl3["sig_ema_long"]]
    disagree = disagree[(disagree["sig_ema_short"] != "neutre") & (disagree["sig_ema_long"] != "neutre")]
    print(f"{len(disagree)}/{len(excl3)} trades exclus (seuil 3/4) ont EMA court et EMA long en désaccord franc (achat vs vente).")
    if len(disagree):
        print(disagree[["date_creation", "ticker", "direction", "sig_ema_short", "sig_ema_long",
                         "sig_macd_short", "sig_macd_long", "r_trailing"]].to_string(index=False))


if __name__ == "__main__":
    main()

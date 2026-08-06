"""
Investigation de l'écart EV test (+1.41R) >> EV train (+0.40-0.57R) trouvé par
walk_forward_ev_robustness.py -- vérifie 4 causes possibles avant de le traiter comme
un vrai edge en amélioration : composition train/test (paires, RR théorique, winrate,
Force), tendance chronologique (EV glissante), significativité (permutation),
contexte de volatilité marché. Le point 1 (biais de sélection lié spécifiquement au
rescraping) n'est PAS vérifiable proprement : le rescraping Force de cette nuit n'a
ajouté AUCUN nouveau trade (100% des clés ticker+date_creation déjà présentes avant,
confirmé plus tôt), seulement enrichi les lignes existantes avec le score Force --
donc aucune trace de provenance par ligne ne permet de distinguer "capturé récemment"
de "toujours présent". Ce point est documenté comme non-vérifiable plutôt qu'ignoré.
"""
import random

import numpy as np
import pandas as pd

import tp_sequence_analysis as tpseq
from trailing_stop_variants import compute_atr

POP_PATH = "population_with_force.csv"
N_PERM = 10000
PERM_SEED = 42


def load_sorted_pop():
    df = pd.read_csv(POP_PATH)
    df["date_creation"] = pd.to_datetime(df["date_creation"])
    return df.sort_values("date_creation").reset_index(drop=True)


def section_composition(train, test, label):
    print(f"\n{'='*100}")
    print(f"3. COMPOSITION TRAIN VS TEST -- {label}")
    print(f"{'='*100}")

    print(f"\nWinrate brut : train {(train['statut_final']=='OBJECTIF ATTEINT').mean()*100:.2f}% "
          f"| test {(test['statut_final']=='OBJECTIF ATTEINT').mean()*100:.2f}%")
    print(f"RR théorique moyen (rr_tp1) : train {train['rr_tp1'].mean():.3f} | test {test['rr_tp1'].mean():.3f}")
    print(f"Force moyen : train {train['score_force'].mean():.3f} | test {test['score_force'].mean():.3f}")

    print(f"\nRépartition par paire (top écarts train vs test, en points de %) :")
    train_pairs = train["ticker"].value_counts(normalize=True) * 100
    test_pairs = test["ticker"].value_counts(normalize=True) * 100
    all_pairs = sorted(set(train_pairs.index) | set(test_pairs.index))
    rows = []
    for p in all_pairs:
        t_pct = train_pairs.get(p, 0.0)
        te_pct = test_pairs.get(p, 0.0)
        rows.append((p, t_pct, te_pct, te_pct - t_pct))
    rows.sort(key=lambda r: abs(r[3]), reverse=True)
    for p, t_pct, te_pct, diff in rows[:6]:
        print(f"  {p:<8} train {t_pct:5.1f}% | test {te_pct:5.1f}% | écart {diff:+5.1f}pt")

    if "timeframe" in train.columns:
        print(f"\nRépartition par timeframe :")
        tf_train = train["timeframe"].value_counts(normalize=True) * 100
        tf_test = test["timeframe"].value_counts(normalize=True) * 100
        for tf in sorted(set(tf_train.index) | set(tf_test.index)):
            print(f"  {tf:<8} train {tf_train.get(tf,0):5.1f}% | test {tf_test.get(tf,0):5.1f}%")


def section_rolling_ev(df):
    print(f"\n{'='*100}")
    print("2. EV EN FENÊTRE GLISSANTE (blocs de 50 trades consécutifs)")
    print(f"{'='*100}")
    window = 50
    for start in range(0, len(df) - window + 1, 25):
        block = df.iloc[start:start + window]
        ev = block["r_trailing"].mean()
        wr = (block["statut_final"] == "OBJECTIF ATTEINT").mean()
        print(f"  Trades {start:>3}-{start+window:<3} ({block['date_creation'].iloc[0].date()} -> "
              f"{block['date_creation'].iloc[-1].date()}) : EV {ev:+.3f}R | winrate {wr*100:.1f}%")

    print(f"\nEV par trimestre calendaire :")
    df2 = df.copy()
    df2["quarter"] = df2["date_creation"].dt.to_period("Q")
    q = df2.groupby("quarter").agg(n=("r_trailing", "size"), ev=("r_trailing", "mean"),
                                     winrate=("statut_final", lambda s: (s == "OBJECTIF ATTEINT").mean()))
    print(q.to_string())


def section_permutation(train, test, full_gap):
    print(f"\n{'='*100}")
    print("4. TEST DE PERMUTATION -- significativité de l'écart test-train")
    print(f"{'='*100}")
    n_train, n_test = len(train), len(test)
    all_r = pd.concat([train, test])["r_trailing"].to_numpy()
    n_total = len(all_r)
    observed_gap = test["r_trailing"].mean() - train["r_trailing"].mean()

    rng = np.random.default_rng(PERM_SEED)
    gaps = np.empty(N_PERM)
    for i in range(N_PERM):
        idx = rng.permutation(n_total)
        test_idx = idx[:n_test]
        train_idx = idx[n_test:]
        gaps[i] = all_r[test_idx].mean() - all_r[train_idx].mean()

    p_value = (np.abs(gaps) >= abs(observed_gap)).mean()
    percentile_rank = (gaps < observed_gap).mean() * 100
    print(f"Écart observé (test - train) : {observed_gap:+.3f}R")
    print(f"Écart moyen sous permutation aléatoire : {gaps.mean():+.4f}R (attendu ~0)")
    print(f"Écart-type des écarts permutés : {gaps.std():.3f}R")
    print(f"P95 des |écarts| permutés : {np.quantile(np.abs(gaps), 0.95):.3f}R")
    print(f"Rang percentile de l'écart observé dans la distribution permutée : {percentile_rank:.2f}%")
    print(f"p-value (bilatéral, {N_PERM} permutations) : {p_value:.4f}")
    if p_value < 0.05:
        print("-> Significatif à 5% : peu probable d'obtenir un écart aussi grand par pur hasard d'assignation.")
    else:
        print("-> NON significatif à 5% : un écart de cette ampleur est plausible par pur hasard "
              "d'assignation train/test sur un échantillon de cette taille.")
    return p_value


def section_volatility_context(df, train, test):
    print(f"\n{'='*100}")
    print("5. CONTEXTE DE VOLATILITÉ MARCHÉ (proxy ATR14/prix, bougies H1 déjà en cache)")
    print(f"{'='*100}")
    print(f"Période train : {train['date_creation'].min().date()} -> {train['date_creation'].max().date()}")
    print(f"Période test  : {test['date_creation'].min().date()} -> {test['date_creation'].max().date()}")

    tickers = sorted(df["ticker"].unique())
    vol_by_period = {"train": [], "test": []}
    for ticker in tickers:
        symbol = tpseq.ticker_to_yahoo_symbol(ticker)
        candles = tpseq.fetch_h1_history(symbol, df["date_creation"].min().to_pydatetime(),
                                          pd.Timestamp.utcnow().tz_localize(None).to_pydatetime())
        if candles is None or candles.empty:
            continue
        candles = compute_atr(candles)
        candles["atr_pct"] = candles["atr"] / candles["close"] * 100
        c_train = candles[(candles["datetime"] >= train["date_creation"].min()) &
                           (candles["datetime"] <= train["date_creation"].max())]
        c_test = candles[(candles["datetime"] >= test["date_creation"].min()) &
                          (candles["datetime"] <= test["date_creation"].max())]
        if not c_train.empty:
            vol_by_period["train"].append(c_train["atr_pct"].mean())
        if not c_test.empty:
            vol_by_period["test"].append(c_test["atr_pct"].mean())

    mean_train_vol = np.mean(vol_by_period["train"])
    mean_test_vol = np.mean(vol_by_period["test"])
    print(f"\nVolatilité moyenne (ATR14/prix %, moyenne des 14 paires) :")
    print(f"  Période train : {mean_train_vol:.4f}%")
    print(f"  Période test  : {mean_test_vol:.4f}%")
    print(f"  Ratio test/train : {mean_test_vol/mean_train_vol:.3f}x")


def main():
    df = load_sorted_pop()
    n = len(df)
    cut = int(round(n * 0.60))
    train = df.iloc[:cut]
    test = df.iloc[cut:].copy()

    print(f"Population : {n} trades ({df['date_creation'].min().date()} -> {df['date_creation'].max().date()})")
    print(f"Split 60/40 -- train n={len(train)} EV={train['r_trailing'].mean():+.3f}R | "
          f"test n={len(test)} EV={test['r_trailing'].mean():+.3f}R")

    print(f"\n{'='*100}")
    print("1. BIAIS DE SÉLECTION LIÉ AU RESCRAPING -- NON VÉRIFIABLE DIRECTEMENT")
    print(f"{'='*100}")
    print("Le rescraping Force de cette nuit a enrichi TOUS les trades existants (100% des clés "
          "ticker+date_creation déjà présentes avant, vérifié précédemment) -- il n'a ajouté aucun "
          "nouveau trade. Il n'existe donc pas de marqueur de provenance par ligne permettant de "
          "distinguer 'capturé récemment' de 'toujours présent dans le dataset'. Ce point ne peut "
          "pas être vérifié proprement avec les données disponibles -- voir section 3 (composition) "
          "pour un test de proxy indirect (Force, RR, paires).")

    section_composition(train, test, "SPLIT 60/40")
    section_rolling_ev(df)
    p_value = section_permutation(train, test, test["r_trailing"].mean() - train["r_trailing"].mean())
    section_volatility_context(df, train, test)

    print(f"\n{'='*100}")
    print("VERDICT")
    print(f"{'='*100}")


if __name__ == "__main__":
    main()

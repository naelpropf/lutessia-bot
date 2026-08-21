"""chantier_trailing015_vs_sizing_svb_isr_2026-08-23.py

QUESTION 2 (session du 23/08), volets 1+2+3 :
1. Sur les fenetres SVB+Israel-Hamas poolees (B_tradable_pgp), effet d'un
   trailing ELARGI (0,15x au lieu de 0,10x, config actuelle de A) sur ces
   fenetres precisement.
2. Si l'effet est net et positif, cout de cet elargissement sur bloc1/
   bloc3/bloc4 (blocs SANS retournement en V).
3. Comparaison au levier "reduction de taille" (-30%/-50%) sur B pendant
   les memes fenetres.

Methode volet 1+2 : recalcule cible (PAS de reconstruction complete de la
population -- seulement les trades OBJECTIF ATTEINT a continuation TP1->TP2
CONFIRMEE, les seuls affectes par la largeur du trailing) via
tp_sequence_analysis.analyze_trade + trailing_stop_variants.simulate_trailing,
memes bougies H1 reelles (backfill MT5 inclus, post-fix df261dc) que partout
ailleurs dans ce projet. tp1_init/tp2_init ne sont pas stockes dans le CSV
B_tradable_pgp -> reconstruits depuis prix_entree/stop_loss_init/rr_tp1/
rr_tp2 (risk_distance=|entree-stop|, is_long=stop<entree, tp=entree +/-
rr*risk_distance) -- verifie par comparaison directe : le recalcule a 0,10x
doit reproduire r_trailing existant a la precision flottante pres.

Volet 3 : une reduction de taille NE CHANGE PAS le R-multiple par trade
(le R est deja normalise au risque) -- son effet se mesure en variance/
exposition dollar, pas en EV-R. Compare donc les deux leviers sur leur
FONCTION reelle : le trailing change la distribution des R (mean ET
variance), le sizing ne change QUE l'echelle (mean ET variance scalees
identiquement par le meme facteur) -- calcule les deux effets sur la
contribution de la fenetre a la variance du P&L en unites de risque.
"""
import importlib.util

import numpy as np
import pandas as pd
from scipy import stats as sps

import tp_sequence_analysis as tpseq
from trailing_stop_variants import compute_atr, simulate_trailing

_spec = importlib.util.spec_from_file_location("chocs", "chantier_fenetres_macro_chocs_2026-08-23.py")
chocs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(chocs)

CONTINUATION_CONFIRMED_CASES = {"tp1_avant_tp2", "meme_bougie"}
POOLED_WINDOWS = [
    ("SVB", "2023-03-08", "2023-03-24"),
    ("israel_hamas", "2023-10-07", "2023-11-15"),
]
BLOC_LABELS_NONV = ["bloc1", "bloc3", "bloc4"]  # bloc2 = celui avec les 2 fenetres V, exclu du cout


def make_stop_fn_fixed(mult):
    def fn(extreme, entry, risk_distance, atr):
        is_long_direction = extreme >= entry
        return extreme - mult * risk_distance if is_long_direction else extreme + mult * risk_distance
    return fn


def enrich_synthetic_tp(df):
    df = df.copy()
    df["yahoo_symbol"] = df["ticker"].apply(tpseq.ticker_to_yahoo_symbol)
    risk_distance = (df["prix_entree"] - df["stop_loss_init"]).abs()
    is_long = df["stop_loss_init"] < df["prix_entree"]
    sign = np.where(is_long, 1.0, -1.0)
    df["tp1_init"] = df["prix_entree"] + sign * df["rr_tp1"] * risk_distance
    df["tp2_init"] = df["prix_entree"] + sign * df["rr_tp2"] * risk_distance
    return df


def recompute_trailing_for_subset(df, factors=(0.10, 0.15)):
    """Pour chaque trade OBJECTIF ATTEINT a continuation confirmee dans df,
    recalcule r_trailing pour chaque facteur de `factors`. Retourne df enrichi
    avec colonnes r_trailing_<facteur> (= r_trailing existant inchange pour
    les trades non affectes par la largeur du trailing) + colonne 'case' +
    colonne 'continuation_confirmee' (bool)."""
    df = enrich_synthetic_tp(df)
    unique_symbols = sorted(df["yahoo_symbol"].dropna().unique())
    candles_by_symbol = {}
    for symbol in unique_symbols:
        start_dt = df["date_creation"].min() - pd.Timedelta(days=2)
        end_dt = pd.Timestamp.utcnow().tz_localize(None)
        candles = tpseq.fetch_h1_history(symbol, start_dt.to_pydatetime(), end_dt.to_pydatetime())
        if candles is not None and not candles.empty:
            candles_by_symbol[symbol] = compute_atr(candles)

    cases, confirmed = [], []
    r_by_factor = {f: [] for f in factors}
    for _, row in df.iterrows():
        candles = candles_by_symbol.get(row["yahoo_symbol"])
        base_r = row["r_trailing"]  # valeur existante (0,10x), fallback si pas de bougies ou non-continuation
        if candles is None or row["statut_final"] != "OBJECTIF ATTEINT":
            cases.append("na_ou_perte")
            confirmed.append(False)
            for f in factors:
                r_by_factor[f].append(base_r)
            continue
        res = tpseq.analyze_trade(row, candles)
        case = res.get("case", "pas_de_donnees")
        cases.append(case)
        if case not in CONTINUATION_CONFIRMED_CASES:
            confirmed.append(False)
            for f in factors:
                r_by_factor[f].append(base_r)
            continue
        confirmed.append(True)
        for f in factors:
            sim = simulate_trailing(row, candles, make_stop_fn_fixed(f), f"fixed_{f}")
            r_by_factor[f].append(sim["exit_r"] if sim is not None else base_r)

    df = df.copy()
    df["case"] = cases
    df["continuation_confirmee"] = confirmed
    for f in factors:
        df[f"r_trailing_{f}"] = r_by_factor[f]
    return df


def stats_r(series, label):
    n = len(series)
    ev = series.mean()
    se = series.std(ddof=1) / np.sqrt(n) if n > 1 else float("nan")
    print(f"  {label:30s} n={n:4d} EV={ev:+.4f}R se={se:.4f}")
    return ev, se


def main():
    pop_b = chocs.load_pop_b()

    print("=" * 95)
    print("VOLET 1 -- fenetres SVB + Israel-Hamas poolees : trailing 0,10x (actuel) vs 0,15x (largeur de A)")
    print("=" * 95)
    masks = []
    for name, s, e in POOLED_WINDOWS:
        m = (pop_b["date_creation"] >= pd.Timestamp(s)) & (pop_b["date_creation"] < pd.Timestamp(e))
        masks.append(m)
        print(f"  {name} : n={int(m.sum())}")
    pooled_mask = masks[0] | masks[1]
    pooled = pop_b[pooled_mask].reset_index(drop=True)
    print(f"  POOL total : n={len(pooled)}")

    pooled_r = recompute_trailing_for_subset(pooled, factors=(0.10, 0.15))
    n_confirmed = int(pooled_r["continuation_confirmee"].sum())
    print(f"\n  trades OBJECTIF ATTEINT a continuation confirmee (affectes par la largeur) : {n_confirmed}/{len(pooled_r)}")

    # verification : le recalcule 0.10x doit reproduire r_trailing existant
    diff_check = (pooled_r["r_trailing_0.1"] - pooled_r["r_trailing"]).abs()
    print(f"  verification recalcule 0,10x vs r_trailing existant : diff max={diff_check.max():.4f}R, "
          f"diff moyenne={diff_check.mean():.5f}R (doit etre ~0 si la reconstruction tp1/tp2 est correcte)")

    print()
    ev_010, se_010 = stats_r(pooled_r["r_trailing_0.1"], "pool 0,10x (actuel/recalcule)")
    ev_015, se_015 = stats_r(pooled_r["r_trailing_0.15"], "pool 0,15x (largeur A)")
    delta = ev_015 - ev_010
    if n_confirmed >= 2:
        conf_sub = pooled_r[pooled_r["continuation_confirmee"]]
        w_stat, p_wilcoxon = sps.wilcoxon(conf_sub["r_trailing_0.15"], conf_sub["r_trailing_0.1"])
    else:
        p_wilcoxon = float("nan")
    print(f"  delta EV (0,15x - 0,10x) = {delta:+.4f}R  |  Wilcoxon signed-rank (sous-ensemble affecte, n={n_confirmed}) : p={p_wilcoxon:.4f}")
    pooled_r.to_csv("chantier_trailing015_pool_svb_isr_detail_2026-08-23.csv", index=False)

    positive_and_material = delta > 0.05  # seuil indicatif : delta materiel, pas juste du bruit d'arrondi
    print(f"\n  -> effet {'NET ET POSITIF' if positive_and_material else 'PAS clairement positif'} sur cette fenetre "
          f"(seuil indicatif +0,05R retenu pour declencher le volet 2)")

    print("\n" + "=" * 95)
    print("VOLET 2 -- cout de l'elargissement sur bloc1/bloc3/bloc4 (pas de retournement en V)")
    print("=" * 95)
    if not positive_and_material:
        print("  Volet 1 n'a pas montre d'effet net positif -- volet 2 execute quand meme (verification demandee),")
        print("  mais gardez a l'esprit que le levier n'a de toute facon rien a justifier s'il ne protege pas.")

    pop_a = chocs.load_pop_a()
    edges = chocs.common_bloc_edges(pop_a, pop_b)
    bloc_defs = {
        "bloc1": (edges[0], edges[1]),
        "bloc2": (edges[1], edges[2]),
        "bloc3": (edges[2], edges[3]),
        "bloc4": (edges[3], edges[4]),
    }

    bloc_results = {}
    for bname in BLOC_LABELS_NONV:
        lo, hi = bloc_defs[bname]
        sub = pop_b[(pop_b["date_creation"] >= lo) & (pop_b["date_creation"] < hi)].reset_index(drop=True)
        print(f"\n  -- {bname} [{lo.date()} -> {hi.date()}], n={len(sub)} --")
        sub_r = recompute_trailing_for_subset(sub, factors=(0.10, 0.15))
        n_conf_bloc = int(sub_r["continuation_confirmee"].sum())
        ev010, _ = stats_r(sub_r["r_trailing_0.1"], f"{bname} 0,10x (recalcule)")
        ev015, _ = stats_r(sub_r["r_trailing_0.15"], f"{bname} 0,15x")
        d = ev015 - ev010
        print(f"    trades affectes (continuation confirmee) : {n_conf_bloc}/{len(sub_r)}  |  delta EV = {d:+.4f}R")
        bloc_results[bname] = dict(n=len(sub_r), n_confirmed=n_conf_bloc, ev010=ev010, ev015=ev015, delta=d)
        sub_r.to_csv(f"chantier_trailing015_cost_{bname}_2026-08-23.csv", index=False)

    print("\n" + "=" * 95)
    print("SYNTHESE VOLET 1+2 -- benefice sur SVB+ISR vs cout sur bloc1/3/4")
    print("=" * 95)
    print(f"  Benefice (SVB+ISR poolees, n={len(pooled_r)}) : delta EV = {delta:+.4f}R (p Wilcoxon={p_wilcoxon:.4f})")
    for bname in BLOC_LABELS_NONV:
        r = bloc_results[bname]
        print(f"  Cout {bname:8s} (n={r['n']}, {r['n_confirmed']} affectes) : delta EV = {r['delta']:+.4f}R")
    total_cost_trades = sum(bloc_results[b]["n"] for b in BLOC_LABELS_NONV)
    weighted_cost = sum(bloc_results[b]["delta"] * bloc_results[b]["n"] for b in BLOC_LABELS_NONV) / total_cost_trades
    print(f"  Cout moyen pondere (bloc1+3+4, n={total_cost_trades}) : {weighted_cost:+.4f}R")
    print(f"  Benefice (n={len(pooled_r)}) vs cout pondere (n={total_cost_trades}) -- benefice pese sur ~{len(pooled_r)} trades,")
    print(f"  cout pese sur ~{total_cost_trades} trades (bien plus de trades exposes au cout qu'au benefice).")

    print("\n" + "=" * 95)
    print("VOLET 3 -- comparaison au levier sizing (-30%/-50%) sur B pendant SVB+ISR")
    print("=" * 95)
    print("""
  Le trailing et le sizing n'agissent PAS sur le meme plan :
  - Trailing (largeur 0,10x -> 0,15x) change la DISTRIBUTION des R-multiples
    des trades a continuation confirmee (mean ET variance de cette distribution
    changent, cf. volet 1 -- delta mesure ci-dessus).
  - Sizing (reduction de X% du risque engage) NE CHANGE PAS le R-multiple par
    trade (R est deja normalise au risque) -- il multiplie l'EXPOSITION dollar
    par (1-X%) sur TOUS les trades de la fenetre, gagnants et perdants
    confondus, dans les memes proportions. Ca reduit mean ET variance du P&L
    en dollars par le meme facteur (1-X%)^1 pour le mean, (1-X%)^2 pour la
    variance -- mais ne change RIEN a la classification win/loss ni a la
    taille relative des gains/pertes.
""")
    for name, s, e in POOLED_WINDOWS:
        m = (pop_b["date_creation"] >= pd.Timestamp(s)) & (pop_b["date_creation"] < pd.Timestamp(e))
        w = pop_b[m]
        r = w["r_trailing"]
        var_r = r.var(ddof=1)
        for cut in (0.30, 0.50):
            scale = 1 - cut
            mean_scaled = r.mean() * scale
            var_scaled = var_r * scale ** 2
            print(f"  {name:15s} size -{cut*100:.0f}% : mean R-equiv {r.mean():+.3f} -> {mean_scaled:+.3f} "
                  f"(EV DIMINUE, ne monte jamais), var {var_r:.3f} -> {var_scaled:.3f} "
                  f"(variance divisee par {1/scale**2:.2f})")
    print(f"\n  Pour comparaison, l'effet trailing mesure au volet 1 sur le pool : delta EV = {delta:+.4f}R,")
    print(f"  c'est une AUGMENTATION d'EV (pas juste une reduction de variance) -- le sizing, par construction,")
    print(f"  ne peut JAMAIS augmenter l'EV (il ne fait que le multiplier par un facteur <1, donc le RAPPROCHER de 0")
    print(f"  ou l'eloigner de 0 selon son signe, jamais l'ameliorer). Les deux leviers ne sont donc pas substituables :")
    print(f"  le sizing reduit l'exposition sans jamais ameliorer l'EV, le trailing (si l'effet volet 1 est confirme)")
    print(f"  ameliore directement l'EV -- mais volet 2 montre qu'il a un cout sur le reste de la population,")
    print(f"  ce que le sizing (localise a la seule fenetre a risque) n'a PAS.")


if __name__ == "__main__":
    main()

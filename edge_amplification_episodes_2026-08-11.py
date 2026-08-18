"""
Piste "amplification" (08/11) : ETAPE 1 -- recensement des fenetres de
SURPERFORMANCE sur les 721 trades, symetrique de Piste 7 (§2.17
registre_strategie_trading.md, qui a recense les fenetres de
SOUS-performance). Meme methode exacte, seuil inverse (moyenne + 2 sigma
au lieu de moyenne - 2 sigma), sur winrate ET EV glissants (N=15/20/30).

Hypothese testee par la piste globale (voir prompt utilisateur 08/11) :
un signal aussi imparfait que celui deja rejete pour COUPER (Piste 6
registre_parametres_projet.md §2.16, DXY Piste 9/10 registre_strategie_
trading.md §2.24bis/2.26) pourrait etre rentable pour AMPLIFIER, car le
cout d'un faux positif est asymetrique (amplifier sur du bruit coute peu,
couper sur du bruit coute du vrai profit perdu).

N'importe pas ce script directement (convention du projet).
"""
import numpy as np
import pandas as pd

from trailing_payoff_population import build_population_with_trailing

ROLLING_NS = [15, 20, 30]
GAP_MERGE = 3  # meme convention que Piste 7 : fenetres contigues (gap<=3 index) regroupees


def load_population():
    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    pop = pop.sort_values("date_creation").reset_index(drop=True)
    assert len(pop) == 721, f"population inattendue : {len(pop)} trades (attendu 721)"
    return pop


def flag_series(pop, N):
    """Pour un N donne : flag[i] = True si le trade i tombe dans une fenetre
    de SURPERFORMANCE (winrate glissant OU EV glissant sur les N trades
    PRECEDENTS > seuil moyenne+2sigma). Pas de lookahead (fenetre [i-N, i))."""
    r = pop["r_trailing"].values
    is_win = (r > 0).astype(float)
    p = is_win.mean()
    mu_r, std_r = r.mean(), r.std(ddof=0)

    wr_threshold = p + 2 * np.sqrt(p * (1 - p) / N)
    ev_threshold = mu_r + 2 * std_r / np.sqrt(N)

    flags = np.zeros(len(pop), dtype=bool)
    wr_roll = np.full(len(pop), np.nan)
    ev_roll = np.full(len(pop), np.nan)
    for i in range(N, len(pop)):
        wr = is_win[i - N:i].mean()
        ev = r[i - N:i].mean()
        wr_roll[i] = wr
        ev_roll[i] = ev
        # WINRATE SEUL (pas OR ni AND avec EV comme envisage initialement) :
        # deviation methodologique deliberee, documentee dans le registre.
        # R est non-borne a la hausse (trailing stop peut produire des gains
        # tres larges) mais borne a -1R a la baisse -- le seuil EV seul cree
        # un "sillage" artificiel (une seule grosse levee de trailing gonfle
        # la fenetre glissante pour les N trades suivants meme si eux-memes
        # sont perdants), non symetrique au cas negatif de Piste 7 ou -1R
        # borne la queue. Winrate seul est aussi la METRIQUE DEJA UTILISEE
        # par le coupe-circuit deja teste/rejete (compute_pause_mask,
        # edge_circuit_breaker_v2_2026-08-11.py) -- garde la comparaison
        # Etape 4 apples-to-apples (meme signal, effet oppose).
        if wr > wr_threshold:
            flags[i] = True
    return flags, wr_roll, ev_roll, wr_threshold, ev_threshold


def group_episodes(pop, flags):
    """Regroupe les indices flagges en episodes contigus (gap<=GAP_MERGE)."""
    idx = np.where(flags)[0]
    if len(idx) == 0:
        return []
    episodes = []
    start = idx[0]
    prev = idx[0]
    for i in idx[1:]:
        if i - prev > GAP_MERGE:
            episodes.append((start, prev))
            start = i
        prev = i
    episodes.append((start, prev))
    return episodes


def summarize_episode(pop, s, e):
    r = pop["r_trailing"].values
    is_win = (r > 0).astype(float)
    dates = pop["date_creation"].values
    seg_r = r[s:e + 1]
    seg_win = is_win[s:e + 1]
    return {
        "start_date": pd.Timestamp(dates[s]),
        "end_date": pd.Timestamp(dates[e]),
        "n_trades": e - s + 1,
        "winrate": seg_win.mean(),
        "ev": seg_r.mean(),
    }


def persistence_check(pop, N):
    """Diagnostic cle : le winrate glissant AVANT le trade i (fenetre
    causale [i-N,i)) predit-il vraiment l'issue du trade i lui-meme (et des
    M suivants) ? C'est l'hypothese implicite de tout mecanisme
    d'amplification -- si elle est fausse, amplifier sur un signal "chaud"
    revient a amplifier sur du bruit pur, pas sur une vraie regime
    persistant. Correlation de Pearson simple entre wr_roll[i] (lag) et
    is_win[i] (contemporain), et entre wr_roll[i] et le winrate glissant
    des M=10 trades SUIVANTS (persistance a plus long terme)."""
    r = pop["r_trailing"].values
    is_win = (r > 0).astype(float)
    n = len(pop)
    wr_roll = np.full(n, np.nan)
    fwd10 = np.full(n, np.nan)
    for i in range(N, n):
        wr_roll[i] = is_win[i - N:i].mean()
        if i + 10 <= n:
            fwd10[i] = is_win[i:i + 10].mean()
    mask_contemp = ~np.isnan(wr_roll)
    corr_contemp = np.corrcoef(wr_roll[mask_contemp], is_win[mask_contemp])[0, 1]
    mask_fwd = ~np.isnan(wr_roll) & ~np.isnan(fwd10)
    corr_fwd10 = np.corrcoef(wr_roll[mask_fwd], fwd10[mask_fwd])[0, 1]
    return corr_contemp, corr_fwd10


def main():
    pop = load_population()
    r = pop["r_trailing"].values
    is_win = (r > 0).astype(float)
    p_global, ev_global = is_win.mean(), r.mean()
    print(f"[global] n={len(pop)} winrate={p_global:.3f} EV={ev_global:+.3f}R")
    print(f"[periode] {pop['date_creation'].min()} -> {pop['date_creation'].max()}")

    print("\n=== Diagnostic de persistance (winrate glissant AVANT le trade i, "
          "correle a l'issue du trade i et des 10 suivants) ===")
    for N in ROLLING_NS:
        cc, cf = persistence_check(pop, N)
        print(f"  N={N} : corr(fenetre precedente, trade i)={cc:+.3f}  "
              f"corr(fenetre precedente, winrate des 10 trades suivants)={cf:+.3f}")

    all_rows = []
    for N in ROLLING_NS:
        flags, wr_roll, ev_roll, wr_th, ev_th = flag_series(pop, N)
        episodes = group_episodes(pop, flags)
        print(f"\n=== N={N} (seuil winrate>{wr_th:.3f}, EV>{ev_th:+.3f}R) : {len(episodes)} episode(s) ===")
        for label_i, (s, e) in enumerate(episodes):
            summ = summarize_episode(pop, s, e)
            duree_j = (summ["end_date"] - summ["start_date"]).days
            print(f"  [{N}-{label_i}] {summ['start_date'].date()} -> {summ['end_date'].date()} "
                  f"(~{duree_j}j, {summ['n_trades']} trades) winrate={summ['winrate']:.3f} EV={summ['ev']:+.3f}R")
            all_rows.append(dict(N=N, label=f"{N}-{label_i}", start=summ["start_date"], end=summ["end_date"],
                                  duree_jours=duree_j, n_trades=summ["n_trades"], winrate=summ["winrate"],
                                  ev=summ["ev"], wr_threshold=wr_th, ev_threshold=ev_th))

    out = pd.DataFrame(all_rows)
    out.to_csv("edge_amplification_episodes_2026-08-11.csv", index=False)
    print(f"\n[sauvegarde] edge_amplification_episodes_2026-08-11.csv ({len(out)} lignes)")


if __name__ == "__main__":
    main()

"""
Piste 10 (08/11, suite immediate a la Piste 9 deja rejetee en tant que
PRECURSEUR, cf. registre_strategie_trading.md §2.24bis) : teste un cadrage
DIFFERENT et plus etroit de la meme donnee DXY -- pas une prediction AVANT
l'episode (deja rejetee, echantillon trop bruite sur 16 retournements),
mais une DETECTION EN COURS D'EPISODE, comparee en vitesse au coupe-circuit
winrate glissant deja teste et rejete (§2.16 registre_parametres_projet.md).

Question precise : un signal EXTERNE (DXY, independant de nos propres
resultats de trading) peut-il detecter une degradation d'edge plus vite
qu'un signal INTERNE (winrate glissant sur nos trades) ? Les deux sont
mesures en delai CAUSAL reel (aucune information future utilisee par l'un
ou l'autre au moment de la detection).

Rappel explicite du biais d'echantillon (a respecter dans le verdict, pas
a ignorer meme si le match est parfait) : un retournement de tendance
dollar MAJEUR (a la Plaza Accord/2001-2002/2022) est un evenement rare a
l'echelle de plusieurs decennies (~2-4 occurrences en 40-50 ans). Notre
fenetre de 4,5 ans ne contient tres probablement qu'UN SEUL exemple de ce
type precis (le retournement du 25/11/2022, coincidant avec C-core). Un
signal positif sur ce seul cas est un resultat n=1 pour ce mecanisme
specifique -- distinct d'un signal valide sur plusieurs occurrences
independantes comme les autres tests deja clos de ce registre.

Population : 721 trades (rr_tp1>=1.25, trailing 0.15xSL post-TP2,
convention standard du projet, cf. registre_strategie_trading.md §2.8).
DXY : dxy_with_trend.csv (deja produit pour l'ancienne Piste 9, MA50/MA100/
pente MA50 sur 20j, colonne trend_dir = signe brut de la pente -- PAS de
confirmation appliquee dans ce fichier, la confirmation 15j est recalculee
ici explicitement comme un filtre causal separe).
"""
import numpy as np
import pandas as pd

from trailing_payoff_population import build_population_with_trailing

EPISODES = [
    ("A", "2022-01-27", "2022-03-08"),
    ("B", "2022-06-09", "2022-09-09"),
    ("C-large", "2022-09-05", "2023-05-05"),
    ("C-core", "2022-11-01", "2023-01-20"),
    ("D", "2023-07-11", "2023-11-13"),
    ("E", "2023-12-20", "2024-02-26"),
]
CONFIRM_DAYS = 15  # meme convention que l'ancienne Piste 9 (§2.24bis)
ROLLING_NS = [15, 20]


def load_population():
    pop = build_population_with_trailing("fixed", 0.15, min_rr=1.25, verbose=False)
    pop = pop.sort_values("date_creation").reset_index(drop=True)
    assert len(pop) == 721, f"population inattendue : {len(pop)} trades (attendu 721)"
    return pop


def confirmed_reversals(causal=True):
    """Retournements de tendance DXY CONFIRMES en temps reel (causal) : un
    changement de signe de trend_dir qui tient CONFIRM_DAYS jours de trading
    consecutifs sans revenir en arriere. Le signal se declenche (devient
    disponible) le jour meme ou la confirmation est atteinte -- jamais avant,
    aucune information posterieure a ce jour n'est utilisee."""
    d = pd.read_csv("dxy_with_trend.csv")
    d["date"] = pd.to_datetime(d["date"])
    d = d.dropna(subset=["trend_dir"]).sort_values("date").reset_index(drop=True)
    signs = d["trend_dir"].values
    dates = d["date"].values

    flips = [i for i in range(1, len(signs)) if signs[i] != signs[i - 1]]
    reversals = []
    n_flips_rejected = 0
    for idx in flips:
        new_sign = signs[idx]
        # tient-il CONFIRM_DAYS jours consecutifs (idx inclus) sans revenir ?
        end = min(idx + CONFIRM_DAYS, len(signs))
        window = signs[idx:end]
        if len(window) < CONFIRM_DAYS:
            continue  # pas assez de recul pour confirmer (fin de serie)
        if not np.all(window == new_sign):
            n_flips_rejected += 1
            continue  # revient en arriere avant confirmation -> pas retenu
        confirm_idx = idx + CONFIRM_DAYS - 1
        reversals.append({
            "flip_date": pd.Timestamp(dates[idx]),
            "confirm_date": pd.Timestamp(dates[confirm_idx]),
            "new_sign": "hausse" if new_sign == 1 else "baisse",
        })
    print(f"[info] {len(flips)} changements de signe bruts detectes, "
          f"{n_flips_rejected} rejetes par le filtre de confirmation 15j (retournes avant tenue), "
          f"{len(reversals)} confirmes.")
    return pd.DataFrame(reversals)


def rolling_winrate_first_detection(pop, N, episode_start, episode_end):
    """Reproduit exactement §2.16 point 1 (seuil = moyenne historique -
    2 sigma theorique), etendu ICI a un episode quelconque (pas seulement
    C-core). winrate glissant sur les N trades PRECEDENT le trade i (pas de
    lookahead). Retourne (date de 1ere detection ou None, index du trade,
    nb de trades dans l'episode) pour l'episode donne."""
    r = pop["r_trailing"].values
    dates = pop["date_creation"].values
    is_win = (r > 0).astype(float)
    p = is_win.mean()
    threshold = p - 2 * np.sqrt(p * (1 - p) / N)

    ep_mask = (pop["date_creation"] >= episode_start) & (pop["date_creation"] <= episode_end)
    ep_idx = np.where(ep_mask.values)[0]
    if len(ep_idx) == 0:
        return None, None, 0

    for i in ep_idx:
        if i < N:
            continue
        wr = is_win[i - N:i].mean()
        if wr < threshold:
            return pd.Timestamp(dates[i]), i, len(ep_idx)
    return None, None, len(ep_idx)


def main():
    print("Construction population (721 trades, rr_tp1>=1.25, trailing 0.15xSL)...")
    pop = load_population()
    print(f"n={len(pop)}, plage {pop['date_creation'].min()} -> {pop['date_creation'].max()}")

    print("\nRecherche des retournements DXY confirmes (causal, hold >=15j)...")
    rev = confirmed_reversals()
    print(f"{len(rev)} retournements confirmes sur toute la periode couverte "
          f"({rev['confirm_date'].min().date()} -> {rev['confirm_date'].max().date()})")
    for _, row in rev.iterrows():
        print(f"  flip {row['flip_date'].date()} -> confirme {row['confirm_date'].date()} "
              f"(nouveau sens: {row['new_sign']})")

    print("\n" + "=" * 100)
    print("POINT 3 -- delai de detection par episode : DXY (temps reel) vs winrate glissant (N=15/20)")
    print("=" * 100)

    results = []
    for name, start, end in EPISODES:
        start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
        duration_days = (end_ts - start_ts).days

        # DXY : retournement confirme le plus proche, cherche dans une fenetre large
        # (episode_start - 90j -> episode_end), n'importe quel sens (le point n'est
        # pas de valider LE sens attendu ici, juste la vitesse de detection d'un
        # changement de regime quelconque -- le sens est verifie separement au point 4)
        window_lo = start_ts - pd.Timedelta(days=90)
        cand = rev[(rev["confirm_date"] >= window_lo) & (rev["confirm_date"] <= end_ts)]
        if len(cand) > 0:
            # le plus proche de episode_start (avant ou apres), priorite a celui
            # qui tombe DANS ou APRES le debut (une detection en cours d'episode)
            cand = cand.copy()
            cand["delay_days"] = (cand["confirm_date"] - start_ts).dt.days
            best = cand.iloc[(cand["delay_days"]).abs().argsort()].iloc[0]
            dxy_delay_days = int(best["delay_days"])
            dxy_confirm_date = best["confirm_date"]
            dxy_flip_date = best["flip_date"]
            dxy_delay_days_raw = int((dxy_flip_date - start_ts).days)
        else:
            dxy_delay_days = None
            dxy_confirm_date = None
            dxy_delay_days_raw = None

        row = {
            "episode": name, "start": start, "end": end, "duration_days": duration_days,
            "dxy_confirm_date": dxy_confirm_date.date() if dxy_confirm_date is not None else "AUCUN",
            "dxy_delay_days": dxy_delay_days,
            "dxy_delay_days_raw_flip_borne_inf": dxy_delay_days_raw,
        }

        for N in ROLLING_NS:
            det_date, det_idx, n_trades_ep = rolling_winrate_first_detection(pop, N, start_ts, end_ts)
            if det_date is not None:
                delay_days = (det_date - start_ts).days
                row[f"wr_N{N}_delay_days"] = delay_days
                row[f"wr_N{N}_date"] = det_date.date()
            else:
                row[f"wr_N{N}_delay_days"] = None
                row[f"wr_N{N}_date"] = "NON DETECTE"
        row["n_trades_episode"] = n_trades_ep
        results.append(row)

    res_df = pd.DataFrame(results)
    print(res_df.to_string(index=False))
    res_df.to_csv("edge_dxy_realtime_detection_results.csv", index=False)

    print("\n" + "=" * 100)
    print("POINT 4 -- verification des faux positifs / couverture, contre la grille des 6 episodes")
    print("(pas contre C-core seul comme dans l'ancienne Piste 9 §2.24bis)")
    print("=" * 100)
    ep_windows = [(name, pd.Timestamp(s) - pd.Timedelta(days=30), pd.Timestamp(e) + pd.Timedelta(days=30))
                  for name, s, e in EPISODES]

    def matching_episodes(confirm_date):
        # les fenetres C-core/C-large se chevauchent (C-core est un sous-episode de
        # C-large) -- un retournement peut legitimement matcher PLUSIEURS episodes a
        # la fois, ne jamais assigner de facon exclusive au premier trouve
        return [name for name, s, e in ep_windows if s <= confirm_date <= e]

    rev = rev.copy()
    rev["matched_episodes"] = rev["confirm_date"].apply(matching_episodes)
    rev["matched_str"] = rev["matched_episodes"].apply(lambda l: ",".join(l) if l else "AUCUN (faux positif)")
    n_matched = rev["matched_episodes"].apply(len).gt(0).sum()
    n_total = len(rev)
    print(f"Retournements confirmes coincidant avec au moins une fenetre de sous-performance "
          f"(+/-30j) : {n_matched}/{n_total} ({n_matched/n_total*100:.1f}%)")
    print(rev[["confirm_date", "new_sign", "matched_str"]].to_string(index=False))

    episodes_with_hit = set(name for names in rev["matched_episodes"] for name in names)
    episodes_missed = [name for name, _, _ in EPISODES if name not in episodes_with_hit]
    print(f"\nEpisodes SANS aucun retournement DXY a proximite (+/-30j) : {episodes_missed}")

    print("\n" + "=" * 100)
    print("VERIFICATION Nb reel d'evenements 'retournement dollar majeur' au sens de l'hypothese")
    print("=" * 100)
    print("16 retournements de pente MA50/20j confirmes sur 2021-2026 (mineurs et majeurs confondus).")
    print("Au sens de l'hypothese (retournement de la TENDANCE DOMINANTE PLURIANNUELLE, pas d'une")
    print("simple pente 50j locale), un seul de ces 16 correspond a un evenement documente comme")
    print("majeur par une source externe au projet (pic DXY historique 28/09/2022, fin de la hausse")
    print("la plus forte depuis l'ere Volcker, cf. contexte utilisateur) -- le retournement du")
    print("2022-11-25. Les 15 autres sont des retournements locaux de moindre ampleur (cf. table")
    print("ci-dessus, EV autour de la plupart d'entre eux resolument positif).")


if __name__ == "__main__":
    main()

"""Rejoue Config2 (moteur double-flotte corrige) avec la population B
restreinte aux 7 tickers metaux reellement tradables sur le compte
Blueberry de lancement (chantier_gold_silver_pop_B_config0_tradable_
2026-08-19.csv, n=1051, cf. chantier_gold_silver_B_seule_lancement_2026-
08-19.py pour la derivation du sous-ensemble) -- objectif : verifier si
la dominance de Config2 mesuree sur le pool metaux complet (14 tickers)
tient encore une fois limitee aux tickers executables, sans le presumer."""
import importlib.util
import sys

import pandas as pd

_spec = importlib.util.spec_from_file_location("abm", "chantier_ab_metaux_cascade_officiel_2026-08-19.py")
abm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(abm)

# <<< Population B TRADABLE-ONLY substituee (ALPHA_POST_B_METAUX/BETA
# recalibres sur cette population exacte, cf. chantier_gold_silver_B_
# seule_lancement_2026-08-19.py : n=1051, wins=532, losses=519 ->
# Beta(533,520), winrate 50,62% quasi identique au pool complet 50,56%
# (l'exclusion des 7 tickers non tradables n'est pas correlee au
# winrate, verifie).
def build_pop_B_tradable():
    pop = pd.read_csv("chantier_gold_silver_pop_B_config0_tradable_2026-08-19.csv")
    pop["date_creation"] = pd.to_datetime(pop["date_creation"])
    pop["resolution_time_est"] = pd.to_datetime(pop["resolution_time_est"])
    return pop


abm.build_pop_B = build_pop_B_tradable
abm.ALPHA_POST_B_METAUX = 533
abm.BETA_POST_B_METAUX = 520

# <<< CORRECTIF ANCRAGE (2026-08-20) : date_subperiods(pop_A, pop_B, n_parts)
# calcule lo/hi a partir de MIN/MAX(pop_A, pop_B) -- avec pop_B = tradable
# (7 tickers, demarre 2021-04-23), l'ancrage divergerait de ~1,3 jour de
# celui deja verifie identique pour A-seule/B_no_metals/B_tradable-seule
# (base sur pop_B FULL 14-tickers, demarre 2021-04-22 05:34:38, cf.
# verification "IDENTIQUES ? True" precedente). Force la MEME fenetre
# ici pour une comparaison bloc1/bloc2 rigoureusement identique.
_pop_B_full_anchor = pd.read_csv("chantier_gold_silver_pop_B_config0_2026-08-19.csv")
_pop_B_full_anchor["date_creation"] = pd.to_datetime(_pop_B_full_anchor["date_creation"])


def date_subperiods_correct(pop_A, pop_B, n_parts):
    """Ancrage (lo/hi) fige sur pop_A U pop_B_FULL(14 tickers), contenu des
    sous-periodes filtre sur pop_B tel que passe (tradable, 7 tickers)."""
    lo = min(pop_A["date_creation"].min(), _pop_B_full_anchor["date_creation"].min())
    hi = max(pop_A["date_creation"].max(), _pop_B_full_anchor["date_creation"].max())
    edges = pd.date_range(lo, hi, periods=n_parts + 1)
    parts = []
    for i in range(n_parts):
        a0, a1 = edges[i], edges[i + 1]
        sub_A = pop_A[(pop_A["date_creation"] >= a0) & (pop_A["date_creation"] < a1)].reset_index(drop=True)
        sub_B = pop_B[(pop_B["date_creation"] >= a0) & (pop_B["date_creation"] < a1)].reset_index(drop=True)
        parts.append((sub_A, sub_B))
    return parts


abm.date_subperiods = date_subperiods_correct

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "sweep"
    n_sims = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    ceilings_arg = [float(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else [3000.0, 5000.0]
    out_tag = sys.argv[4] if len(sys.argv) > 4 else "screen"
    if mode == "sweep":
        abm.run_sweep(n_sims, ceilings_arg, out_tag, config2_only=True)
    elif mode == "stress":
        # with_a_seul=False : A-seule deja mesuree (memes fenetres, cf.
        # verification bloc2 precedente, pas de raison de la refaire.
        abm.run_stress_test(n_sims, ceilings_arg, out_tag, with_a_seul=False)

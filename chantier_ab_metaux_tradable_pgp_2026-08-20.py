"""chantier_ab_metaux_tradable_pgp_2026-08-20.py

Branche le moteur cascade officiel (chantier_ab_metaux_cascade_officiel_
2026-08-19.py) sur la population B_tradable FINALE = gold/silver (7 tickers
tradables, n=1051, cf. chantier_ab_metaux_tradable_config2_2026-08-19.py)
+ Palladium (n=102) + Platinum (n=95), Natural Gas EXCLU (decision actee
08/20 : EV non significative p=0,07, echantillon trop mince). Meme
methodologie d'integration que gold/silver -- meme pipeline (rr_threshold_
test.build_extended_population -> tp2_realistic_payoff -> trailing 0,10x,
cf. gaz_palladium_platine_population_2026-08-20.py, copie a l'identique de
or_argent_population_2026-08-19.py), meme logique de routage vers B.
Tradabilite BB des 2 tickers deja confirmee (meme compte que gold/silver,
pas revalidee ici).

Population fusionnee : chantier_gold_silver_pop_B_config0_tradable_2026-
08-19.csv (n=1051) + gaz_palladium_platine_population_trailing_2026-08-20.
csv filtre a PALLADIUM/PLATINUM uniquement (n=197), triee par date_creation
(ordre chronologique preserve, meme convention que build_extended_
population). n final = 1248.

Prior corrige -- ETAT ANTERIEUR (verifie par citation, cf. Partie 2 de la
demande utilisateur) :
- chantier_b6_montecarlo_2026-08-19.py utilise ALPHA_POST_B/BETA_POST_B=
  276,297 -- derive sur build_pop_B_variant() (571 trades SANS metaux),
  MAIS reste le prior correct POUR SON PROPRE PERIMETRE (b6, sans metaux),
  documente comme tel dans registre_parametres_projet.md:4642-4643. PAS le
  prior utilise par le moteur cascade officiel.
- chantier_ab_metaux_cascade_officiel_2026-08-19.py:130 utilise DEJA
  ALPHA_POST_B_METAUX,BETA_POST_B_METAUX=762,745 -- PAS 276/297 (ce bug-la
  etait deja corrige le 08/19, cf. registre_parametres_projet.md:4629-4643)
  -- mais 762/745 est derive sur le POOL METAUX COMPLET 14 tickers (n=1505,
  build_pop_B() par defaut charge chantier_gold_silver_pop_B_config0_2026-
  08-19.csv ligne 746), PAS sur B_tradable (7 tickers, n=1051, la
  population REELLEMENT retenue pour le lancement, §6.5 du registre
  strategie). Le prior explicitement calibre pour B_tradable seule
  (ALPHA_POST_B_TRADABLE=533, BETA_POST_B_TRADABLE=520) n'est branche que
  par le wrapper chantier_ab_metaux_tradable_config2_2026-08-19.py -- le
  fichier "officiel" lui-meme, invoque nu, reste desaligne avec la
  population de lancement reelle (ecart deja present AVANT ce chantier-ci,
  independant de palladium/platine).

Prior FINAL (cette session, meme methode Beta(1,1)+wins/losses observes,
verifie par calcul direct sur le CSV fusionne) :
n=1248, wins=624 (532 B_tradable + 92 Pd/Pt), losses=624 (519 B_tradable +
105 Pd/Pt) -> Beta(625, 625), winrate exactement 50,00%.
"""
import importlib.util

import pandas as pd

_spec = importlib.util.spec_from_file_location("abm", "chantier_ab_metaux_cascade_officiel_2026-08-19.py")
abm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(abm)

POP_B_TRADABLE_PGP_PATH = "chantier_gold_silver_pop_B_tradable_pgp_2026-08-20.csv"

ALPHA_POST_B_TRADABLE_PGP = 625
BETA_POST_B_TRADABLE_PGP = 625


def build_pop_B_tradable_pgp():
    pop = pd.read_csv(POP_B_TRADABLE_PGP_PATH)
    pop["date_creation"] = pd.to_datetime(pop["date_creation"])
    pop["resolution_time_est"] = pd.to_datetime(pop["resolution_time_est"])
    return pop


# <<< Branchement population + prior corriges (remplace le defaut "officiel"
# 762/745 + pool 14 tickers, desaligne avec B_tradable, cf. docstring) -->
abm.build_pop_B = build_pop_B_tradable_pgp
abm.ALPHA_POST_B_METAUX = ALPHA_POST_B_TRADABLE_PGP
abm.BETA_POST_B_METAUX = BETA_POST_B_TRADABLE_PGP


if __name__ == "__main__":
    pop_B = abm.build_pop_B()
    n = len(pop_B)
    wins = (pop_B["statut_final"] == "OBJECTIF ATTEINT").sum()
    losses = (pop_B["statut_final"] == "INVALIDÉE").sum()
    print(f"Population B_tradable+Pd+Pt branchee dans le moteur officiel : n={n}")
    print(f"wins={wins} losses={losses} (somme={wins + losses}, doit valoir n)")
    print(f"Prior branche : Beta({abm.ALPHA_POST_B_METAUX}, {abm.BETA_POST_B_METAUX})")
    assert n == 1248, f"Taille de population inattendue: {n} (attendu 1248)"
    assert wins + losses == n, "Trades non resolus dans la population finale (inattendu)"
    assert abm.ALPHA_POST_B_METAUX == 625 and abm.BETA_POST_B_METAUX == 625
    print("\nOK -- moteur cascade officiel pret avec population+prior corriges.")
    print("Aucun run n=300/n=600 lance ici (hors perimetre de ce chantier).")

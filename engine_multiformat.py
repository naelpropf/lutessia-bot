"""
Etape B (08/08) : moteur generique multi-phase / multi-format, en remplacement
du moteur 1-phase flat (CHALLENGE_TARGET_PCT=8.0/MIN_TRADING_DAYS=4/BREAK_DD_PCT
=10.0 dans scaling_simulation.py:48-50) utilise partout ailleurs dans le projet.

Ne remplace PAS les scripts existants (point2_sequencing_engine.py,
extra_account_v4_multi.py, extra_account_v4_multi_stagger.py,
extra_account_v4_cascade_check.py) -- ceux-ci restent la reference pour
reproduire le chiffre verrouille actuel (5 794 566$/5 898 897$, n=600). Ce
module sert au nouveau travail de comparaison de formats (Etape C/D).

Donnees FORMATS peuplees depuis etape_a_formats_comptes_propfirms_2026-08-08.md
(recherche officielle du 08/08). Chaque FormatDef porte ses notes de confiance
-- ne pas traiter un champ "moyenne"/"faible" comme aussi fiable qu'un champ
"elevee" lors de l'interpretation des resultats.

Constat cle (Etape A) qui structure ce moteur : le DD max est STATIQUE pour
tout format avec evaluation (1/2/3-step, quel que soit le nombre de phases) et
TRAILING pour tout format instant funding, avec deux variantes trailing :
  - trailing_peak : suit le pic d'equite en continu, peut se VERROUILLER
    (freeze au solde de depart / breakeven) une fois un seuil de profit
    atteint (Blueberry Instant Elite/Lite, FundedNext Stellar Instant, GFT
    Instant) -- via lock_after_pct.
  - trailing_eod : recalcule une fois par jour sur le plus haut solde de
    CLOTURE atteint parmi tous les jours precedents (FTMO 1-Step, cas limite
    -- pas un vrai trailing intraday comme les instant funding).
"""
import robustness_5ers_risk_challenge as eng

DAY_SECONDS = 86400


# ---------------------------------------------------------------------------
# Structures
# ---------------------------------------------------------------------------

def phase(target_pct, min_days, dd_daily_pct, dd_max_pct, dd_max_mode, lock_after_pct=None):
    """dd_max_mode : "static" | "trailing_peak" | "trailing_eod".
    target_pct/min_days peuvent etre None pour un phase "funded" ou un format
    instant funding sans cible formelle."""
    assert dd_max_mode in ("static", "trailing_peak", "trailing_eod")
    return dict(target_pct=target_pct, min_days=min_days, dd_daily_pct=dd_daily_pct,
                dd_max_pct=dd_max_pct, dd_max_mode=dd_max_mode, lock_after_pct=lock_after_pct)


def format_def(firm, format_name, phases, funded=None, price=None, copytrade_cap=None,
               copytrade_confirmed=False, max_accounts=None, confidence_notes=""):
    """phases : liste de phase() dans l'ordre P1->P2->...->funded.
    funded : phase() separee si les parametres finances different de la
    derniere phase d'evaluation (sinon None -> reprend la derniere phase)."""
    return dict(firm=firm, format_name=format_name, phases=phases,
                funded=funded if funded is not None else phases[-1],
                price=price or {}, copytrade_cap=copytrade_cap,
                copytrade_confirmed=copytrade_confirmed, max_accounts=max_accounts,
                confidence_notes=confidence_notes)


# ---------------------------------------------------------------------------
# Registre FORMATS -- source : etape_a_formats_comptes_propfirms_2026-08-08.md
# ---------------------------------------------------------------------------

FORMATS = {}

# --- FTMO --------------------------------------------------------------
FORMATS["FTMO_2Step_Standard"] = format_def(
    "FTMO", "2-Step Standard",
    phases=[phase(10.0, 4, 5.0, 10.0, "static"), phase(5.0, 4, 5.0, 10.0, "static")],
    price={50000: 345, 100000: 439, 200000: 1080},
    copytrade_cap=400000, copytrade_confirmed=False,
    confidence_notes="Phases/DD elevee. Copytrade: tolere sous plafond, pas de phrase 'autorise' explicite (confiance moyenne). Plafond 400k finance-seul ou +evaluation : non tranche.")

FORMATS["FTMO_2Step_Swing"] = format_def(
    "FTMO", "2-Step Swing (actuel projet)",
    phases=[phase(10.0, 4, 5.0, 10.0, "static"), phase(5.0, 4, 5.0, 10.0, "static")],
    price={50000: 345, 100000: 439, 200000: 1080},
    copytrade_cap=400000, copytrade_confirmed=False,
    confidence_notes="Memes phases/DD que Standard (aucune valeur differente trouvee officiellement, confiance moyenne sur l'absence de difference). Levier 1:30 vs 1:100 (confiance moyenne, pas de citation verbatim). Prix Swing non liste separement -- suppose identique Standard, NON confirme (faible).")

FORMATS["FTMO_1Step"] = format_def(
    "FTMO", "1-Step",
    phases=[phase(10.0, 0, 3.0, 10.0, "trailing_eod")],
    price={50000: 319, 100000: 499, 200000: 999},
    copytrade_cap=400000, copytrade_confirmed=True,
    confidence_notes="Cas limite trailing : recalcule a minuit sur le plus haut solde de CLOTURE (pas intraday comme les vrais instant funding). 'Best Day Rule' 50% non modelisee ici (contrainte de repartition des gains, pas un DD). Split 90% direct. COPYTRADE confirme 08/08 via reponse support FTMO (utilisateur) : 'Yes. Copy trading is allowed at FTMO as long as you are personally managing the accounts and your setup does not exceed the maximum capital allocation of $400,000 ... per trader' -- reponse generale FTMO, pas de restriction mentionnee sur le 1-Step specifiquement, mais pas de carve-out non plus (meme plafond 400k que le 2-Step deja confirme par le FAQ officiel).")

# --- The5%ers ------------------------------------------------------------
FORMATS["Fivers_HighStakes"] = format_def(
    "The5%ers", "High Stakes (actuel projet)",
    phases=[phase(8.0, 3, 5.0, 10.0, "static"), phase(5.0, 3, 5.0, 10.0, "static")],
    price={100000: 545},
    copytrade_cap=500000, copytrade_confirmed=True,
    confidence_notes="Phases/DD elevee (deja utilise dans le moteur actuel). Copytrade + plafond 500k : confiance moyenne, corrobore par precision utilisateur + sources tierces, pas de page officielle unique retrouvee. Variante d'entree a 10% (au lieu de 8%) possible en P1 -- non modelisee, confiance moyenne sur laquelle le projet utilise reellement.")

FORMATS["Fivers_HyperGrowth"] = format_def(
    "The5%ers", "Hyper Growth (\"Instant Funding\")",
    phases=[phase(10.0, 0, 3.0, 6.0, "trailing_peak")],
    price={10000: 260, 20000: 450, 40000: 850},
    copytrade_cap=500000, copytrade_confirmed=True,
    confidence_notes="Pas un vrai instant funding sans condition -- cible residuelle 10% mais argent reel des J1. DD journalier 3% = PAUSE (pas fermeture), non modelise ici (le moteur traite toute casse comme un reset payant, simplification a corriger si ce format est retenu serieusement). DD max reellement trailing (monte avec le solde) -- pas de seuil de verrouillage documente, lock_after_pct=None ici (a verifier). Capital max en evaluation 40k$ (taille max testee). COPYTRADE reconfirme 08/08 via reponse support The5%ers (utilisateur), specifique a Hyper Growth : 'Copy trading is allowed on Hyper Growth instant-funding accounts only when you are copying trades from your own accounts, including other prop firm or personal accounts... copying trades between two different Bootcamp accounts is not allowed... once you manage more than $500K in capital across all accounts and programs, you are no longer permitted to copy trades' -- plafond 500k confirme par la meme reponse.")

FORMATS["Fivers_ProGrowth"] = format_def(
    "The5%ers", "Pro Growth",
    phases=[phase(10.0, 3, 3.0, 6.0, "static")],
    price={},
    copytrade_cap=500000, copytrade_confirmed=False,
    confidence_notes="Toutes valeurs confiance MOYENNE (recherche agregee, pas de fetch officiel direct). Trailing/statique du DD max NON confirme separement -- suppose statique par analogie avec les autres formats eval, A VERIFIER avant usage serieux. DD journalier ferme le compte (pas de pause, contrairement a Hyper Growth).")

# --- Blueberry Funded ------------------------------------------------------
# RESOLU 08/12 (chantier cluster Blueberry 1,5%) : le compte 2-step reellement
# souscrit en live est le "2-Step Challenge" standard (10%/5%, DD 5%/10%),
# PAS Prime -- confirme par l'utilisateur. CONFIG_REF (etape_e_fleet_
# integration.py:123-125, utilise par toute la reference officielle du
# projet, §1.8 du registre) utilisait jusqu'ici Blueberry_Prime2Step -- donc
# la reference officielle actuelle simule en realite le MAUVAIS produit
# Blueberry (Prime, moins cher, sans restriction cluster) au lieu du produit
# reellement trade (Standard, plus cher, SOUMIS a la restriction cluster).
# Voir le chantier "cluster Blueberry 1,5%" (session_handoff_2026-08-12.md,
# registre §2.59+) pour la comparaison des options A (basculer reellement sur
# Prime) / B (rester Standard, modeliser le vrai cluster) / C (retirer
# Blueberry). Les deux formats restent modelises separement ci-dessous.
FORMATS["Blueberry_Prime2Step"] = format_def(
    "Blueberry", "Prime Challenge (2-Step)",
    phases=[phase(8.0, 5, 4.0, 10.0, "static"), phase(6.0, 5, 4.0, 10.0, "static")],
    price={25000: 165},
    copytrade_cap=450000, copytrade_confirmed=False,
    confidence_notes="Phases/DD elevee. NE PAS confondre avec 'Instant Access Elite/Lite' (produit instant funding separe, ambiguite resolue Etape A) -- le split 80%/jour1 cite dans les docs 06-07/08 pour 'Instant Access' concernait le mauvais produit.")

FORMATS["Blueberry_2StepStandard"] = format_def(
    "Blueberry", "2-Step Challenge (standard, plus ancien)",
    phases=[phase(10.0, 3, 5.0, 10.0, "static"), phase(5.0, 3, 5.0, 10.0, "static")],
    price={25000: 170},
    copytrade_cap=450000, copytrade_confirmed=False,
    confidence_notes="Matche les valeurs dd=5.0/dd_max=10.0 actuellement codees dans point2_sequencing_engine.py:57 (moteur perime, plus utilise par la reference officielle). CONFIRME 08/12 par l'utilisateur : c'est le produit reellement souscrit en live (pas Prime), ET la regle de budget de risque cluster FX Majors (1,5% partage entre positions simultanees) s'applique specifiquement a CE format -- pas a Prime. Prix 25k=170$ source tradingpilot.com (table complete 5K=48$/10K=70$/25K=170$/50K=315$/100K=620$/200K=1240$, progression coherente), remplace le None precedent.")

FORMATS["Blueberry_1Step"] = format_def(
    "Blueberry", "1-Step Challenge",
    phases=[phase(10.0, 3, 4.0, 6.0, "static")],
    price={25000: None},
    copytrade_cap=450000, copytrade_confirmed=False,
    confidence_notes="Prix palier 25k non isole dans les sources (faible confiance). Reste elevee sur phases/DD.")

FORMATS["Blueberry_InstantElite"] = format_def(
    "Blueberry", "Instant Elite (instant funding)",
    phases=[],
    funded=phase(None, None, None, 10.0, "trailing_peak", lock_after_pct=10.0),
    price={25000: 800},
    copytrade_cap=450000, copytrade_confirmed=True,
    confidence_notes="0 phase d'evaluation, financement direct. DD journalier: AUCUNE limite (non modelise -- ne pas fixer dd_daily_pct a une valeur arbitraire, laisser None et adapter process_trade_mf pour ignorer le check journalier si None). Plancher ne se reinitialise JAMAIS apres un retrait -- non modelise ici, risque structurel a ajouter si ce format est retenu serieusement. Prix confiance faible-moyenne (source tierce). COPYTRADE confirme 08/08 via reponse support Blueberry (utilisateur) : 'Yes, you can copy trade... using various copy trade software... to copy trade between accounts you own... copy trading is only permitted between accounts under your ownership even if they are on different platforms' -- reponse generale Blueberry, pas de carve-out Instant Elite specifique mais aucune restriction par format mentionnee non plus.")

FORMATS["Blueberry_InstantLite"] = format_def(
    "Blueberry", "Instant Lite (instant funding)",
    phases=[],
    funded=phase(None, None, 2.0, 4.0, "trailing_peak", lock_after_pct=4.0),
    price={25000: 185},
    copytrade_cap=450000, copytrade_confirmed=False,
    confidence_notes="Meme mecanisme de verrouillage qu'Instant Elite mais marge de base 4x plus etroite (4% vs 10%). Prix moyenne des fourchettes tierces trouvees (145-225$), faible confiance.")

# --- GFT (Goat Funded Trader) ----------------------------------------------

# Prix GFT : AUCUNE grille officielle chiffree trouvee (site a selecteur JS,
# pages FAQ officielles sans prix). Recherche complementaire ciblee (08/08)
# n'a trouve que des sources tierces contradictoires (ecarts 20-40% entre
# elles, coherent avec des promos permanentes type The5%ers) -- confiance
# MOYENNE partout, table la plus complete (FXEmpire) retenue par defaut.
# A remplacer par une capture manuelle du selecteur officiel si un calcul
# financier serieux en depend.
FORMATS["GFT_2Step_GOAT"] = format_def(
    "GFT", "2-Step GOAT Model (actuel projet)",
    phases=[phase(8.0, 3, 4.0, 10.0, "static"), phase(6.0, 3, 4.0, 10.0, "static")],
    price={25000: 148, 50000: 288, 100000: 458},
    copytrade_cap=400000, copytrade_confirmed=False,
    confidence_notes="DD max STATIQUE confirme officiellement ('Absolute Floor'), CONTREDIT l'hypothese initiale du projet qui le supposait trailing -- correction importante. Copytrade: regle generale plateforme uniquement, pas confirme par format. PRIX : un seul chiffre tiers (458$/100k, FXEmpire) non corrobore par une 2e source independante ni le site officiel -- confiance FAIBLE sur le prix specifiquement (moyenne sur le reste). Une autre source tierce (PropTradingVibes) donne des valeurs bien plus basses (probablement une promo au moment du scrape) -- ecart 20-40% typique, non reconcilie.")

FORMATS["GFT_2Step_Standard"] = format_def(
    "GFT", "2-Step Standard",
    phases=[phase(10.0, 3, 5.0, 10.0, "static"), phase(5.0, 3, 5.0, 10.0, "static")],
    price={25000: 228, 50000: 338, 100000: 594, 200000: 1174},
    copytrade_cap=400000, copytrade_confirmed=False,
    confidence_notes="Elevee sur phases/DD. Prix confiance MOYENNE (source tierce FXEmpire uniquement, non recoupe).")

FORMATS["GFT_3Step"] = format_def(
    "GFT", "3-Step",
    phases=[phase(6.0, None, 4.0, 8.0, "static"), phase(6.0, None, 4.0, 8.0, "static"), phase(6.0, None, 4.0, 8.0, "static")],
    price={25000: 145, 50000: 225, 100000: 365, 200000: 665},
    copytrade_cap=400000, copytrade_confirmed=False,
    confidence_notes="Aucun minimum de jours en evaluation (min_days=None -- process_trade_mf doit traiter None comme 'pas de contrainte'). DD max statique confirme (8%, 'never drop below 92%'). Prix confiance MOYENNE (source tierce, un seul point 200k non recoupe).")

FORMATS["GFT_1Step"] = format_def(
    "GFT", "1-Step",
    phases=[phase(10.0, 3, 4.0, 6.0, "static")],
    price={25000: 248, 50000: 358, 100000: 618, 200000: 1098},
    copytrade_cap=400000, copytrade_confirmed=False,
    confidence_notes="DD journalier 3% pour comptes achetes a partir du 01/08/2026 (avant : 4%) -- valeur post-01/08 retenue ici. DD max statique confirme (6%). Prix confiance MOYENNE (source tierce FXEmpire).")

FORMATS["GFT_InstantGOAT"] = format_def(
    "GFT", "Instant GOAT",
    phases=[],
    funded=phase(None, None, 3.0, 6.0, "trailing_peak"),
    price={25000: 318, 50000: 488, 100000: 838, 200000: 1708},
    copytrade_cap=400000, copytrade_confirmed=True,
    confidence_notes="DD max trailing confirme (libelle 'Trailing' explicite), pas de lock_after_pct documente (a verifier). Contrainte cachee non modelisee : fermeture definitive si PnL flottant < -2% du solde a tout instant (regle intraday plus stricte que le DD max lui-meme). PRIX FAIBLE confiance : 3 sources tierces donnent 3 chiffres differents pour 100k (838$ FXEmpire retenu ici, vs 767$/575$ promo selon TradeLocker Hub, vs 263$/438$ selon le site officiel mais sur un modele Instant potentiellement different) -- non reconcilie, a verifier manuellement. COPYTRADE confirme 08/08 via reponse support GFT (utilisateur) : 'Copy trading is allowed only between your own funded accounts, including instant accounts... Copy trading is not permitted between challenge or evaluation accounts, or from an evaluation account to a funded account' -- confirme explicitement pour les comptes instant (donc Instant GOAT une fois finance, ce qui est immediat pour ce format).")

FORMATS["GFT_InstantPRO"] = format_def(
    "GFT", "Instant PRO",
    phases=[],
    funded=phase(None, None, None, 4.0, "trailing_peak"),
    price={25000: 328, 50000: 498, 100000: 858},
    copytrade_cap=400000, copytrade_confirmed=False,
    confidence_notes="INCOHERENCE NON RESOLUE : DD max trouve a 4% trailing sur une source, 8% trailing sur une autre passe de recherche -- confiance FAIBLE, a reverifier manuellement avant tout usage serieux. Aucun DD journalier (confirme, dd_daily_pct=None). Prix confiance MOYENNE (source tierce FXEmpire uniquement).")

# --- FundedNext --------------------------------------------------------
FORMATS["FundedNext_Stellar2Step"] = format_def(
    "FundedNext", "Stellar 2-Step",
    phases=[phase(8.0, 5, 5.0, 10.0, "static"), phase(5.0, 5, 5.0, 10.0, "static")],
    price={200000: 1099.99},
    copytrade_cap=300000, copytrade_confirmed=True,
    confidence_notes="Elevee sur tout. Copytrade confirme en detail (autorise meme trader en challenge, interdit entre traders, interdit sur finance sauf inter-comptes FundedNext <=300k).")

FORMATS["FundedNext_StellarLite"] = format_def(
    "FundedNext", "Stellar Lite (actuel projet)",
    phases=[phase(8.0, 5, 4.0, 8.0, "static"), phase(4.0, 5, 4.0, 8.0, "static")],
    price={200000: 798.99},
    copytrade_cap=300000, copytrade_confirmed=True,
    confidence_notes="Elevee sur tout (deja corrige dans le moteur actuel, reconfirme officiellement statique ici).")

FORMATS["FundedNext_Stellar1Step"] = format_def(
    "FundedNext", "Stellar 1-Step",
    phases=[phase(10.0, 2, 3.0, 6.0, "static")],
    price={200000: 1099.99},
    copytrade_cap=300000, copytrade_confirmed=True,
    confidence_notes="Elevee. 2 jours minimum (non consecutifs, 1 trade/jour min -- simplifie ici en min_days=2).")

FORMATS["FundedNext_StellarInstant"] = format_def(
    "FundedNext", "Stellar Instant",
    phases=[],
    funded=phase(None, None, None, 6.0, "trailing_peak"),
    price={20000: None},
    copytrade_cap=300000, copytrade_confirmed=True,
    confidence_notes="INADAPTE au palier actuel du projet (200k$) -- plafonne a 20k$ seulement, pas de palier 200k. A garder pour reference mais exclure de toute comparaison au palier actuel. Copytrade autorise entre comptes Stellar Instant du meme trader, mais interdit avec Stellar 1/2-Step/Lite meme pour le meme individu (regle plus stricte que les autres firms).")


# ---------------------------------------------------------------------------
# Compte + moteur de simulation
# ---------------------------------------------------------------------------

def make_acc_mf(fmt, palier, cost, active=True):
    acc = eng.make_acc(palier, cost, active=active)
    acc["format"] = fmt["format_name"]
    acc["phase_index"] = 0
    acc["locked_peak"] = None       # pour trailing_peak + lock_after_pct
    acc["eod_peak"] = 0.0           # pour trailing_eod
    acc["last_day_seen"] = None
    if not fmt["phases"]:
        # Instant funding : 0 phase d'evaluation, financement direct des l'ouverture.
        acc["phase"] = "funded"
    return acc


def _current_phase(fmt, acc):
    if acc["phase"] == "funded":
        return fmt["funded"]
    return fmt["phases"][acc["phase_index"]]


def _reset_trackers(acc):
    acc["cumulative_since_reset"] = 0.0
    acc["peak_since_reset"] = 0.0
    acc["trading_days_since_reset"] = set()
    acc["daily_pnl"] = {}
    acc["locked_peak"] = None
    acc["eod_peak"] = 0.0
    acc["last_day_seen"] = None


def _dd_max_breached(acc, pdef, close_day):
    """Retourne True si le DD max (statique ou trailing selon pdef) est
    depasse. Suppose que cumulative_since_reset/peak_since_reset viennent
    d'etre mis a jour pour le trade courant."""
    if pdef["dd_max_pct"] is None:
        return False
    threshold = pdef["dd_max_pct"] / 100 * acc["palier"]

    if pdef["dd_max_mode"] == "static":
        # Plancher fixe sur le solde de depart -- ne bouge jamais.
        return -acc["cumulative_since_reset"] >= threshold

    if pdef["dd_max_mode"] == "trailing_peak":
        lock_pct = pdef.get("lock_after_pct")
        if lock_pct is not None:
            if acc["locked_peak"] is None and acc["peak_since_reset"] >= lock_pct / 100 * acc["palier"]:
                acc["locked_peak"] = acc["peak_since_reset"]
            if acc["locked_peak"] is not None:
                # Plancher verrouille au niveau atteint lors du declenchement
                # (breakeven ou mieux) -- ne remonte plus avec le pic apres.
                trailing_dd = acc["locked_peak"] - acc["cumulative_since_reset"]
                return trailing_dd >= threshold
        trailing_dd = acc["peak_since_reset"] - acc["cumulative_since_reset"]
        return trailing_dd >= threshold

    if pdef["dd_max_mode"] == "trailing_eod":
        # Recalcule une fois par jour sur le plus haut solde de CLOTURE
        # atteint parmi tous les jours precedents (pas intraday).
        if acc["last_day_seen"] is None:
            acc["last_day_seen"] = close_day
        elif close_day > acc["last_day_seen"]:
            acc["eod_peak"] = max(acc["eod_peak"], acc["cumulative_since_reset"])
            acc["last_day_seen"] = close_day
        trailing_dd = acc["eod_peak"] - acc["cumulative_since_reset"]
        return trailing_dd >= threshold

    raise ValueError(f"dd_max_mode inconnu: {pdef['dd_max_mode']}")


def process_trade_mf(acc, trade, now, fmt, state, risk_pct, market_data, excluded_map,
                      split_flat=0.80, reserve_share=0.95, cost_override=None):
    """Version generalisee de process_trade (extra_account_v4_multi_stagger.py:
    157-220), parametree par FormatDef au lieu d'une cible/DD globale unique.
    Retourne True si ce trade vient de faire passer le compte en 'funded'
    pour la premiere fois (comme extra_account_v4_multi_stagger.process_trade)."""
    if not acc["active"]:
        return False
    close_time = now + trade["hold_seconds"]
    acc["open_positions"] = [(t, c) for (t, c) in acc["open_positions"] if c > now]
    if len(acc["open_positions"]) >= eng.MAX_POSITIONS:
        return False
    if any(t in excluded_map[trade["ticker"]] for (t, _) in acc["open_positions"]):
        return False

    eff_risk, _ = eng.feasible_risk_pct(trade["ticker"], trade["sl_distance"], acc["palier"], risk_pct, market_data)
    risk_amount = eff_risk / 100 * acc["palier"]
    pnl = trade["outcome_r"] * risk_amount

    acc["open_positions"].append((trade["ticker"], close_time))
    acc["cumulative_since_reset"] += pnl
    acc["peak_since_reset"] = max(acc["peak_since_reset"], acc["cumulative_since_reset"])
    acc["trading_days_since_reset"].add(int(now // DAY_SECONDS))
    acc["trades_taken"] += 1
    close_day = int(close_time // DAY_SECONDS)
    acc["daily_pnl"][close_day] = acc["daily_pnl"].get(close_day, 0.0) + pnl

    pdef = _current_phase(fmt, acc)

    if acc["phase"] == "funded":
        net_pnl = pnl * split_flat if pnl > 0 else pnl
        acc["total_funded_pnl"] += net_pnl
        if net_pnl > 0:
            state["reserve"] += net_pnl * reserve_share

    daily_broke = False
    if pdef["dd_daily_pct"] is not None:
        daily_dd = -acc["daily_pnl"][close_day]
        daily_broke = daily_dd >= pdef["dd_daily_pct"] / 100 * acc["palier"]
    max_broke = _dd_max_breached(acc, pdef, close_day)

    if daily_broke or max_broke:
        state["total_breaks"] += 1
        cost = cost_override if cost_override is not None else acc["cost"]
        if state["reserve"] >= cost:
            state["reserve"] -= cost
        else:
            shortfall = cost - state["reserve"]
            state["reserve"] = 0.0
            if not state.get("ever_funded"):
                state["real_cash_paid"] = state.get("real_cash_paid", 0.0) + shortfall
        acc["total_fees_paid"] += cost
        if fmt["phases"]:
            # Format avec evaluation : la casse repaye le challenge, repart phase 1.
            acc["phase"] = "challenge"
            acc["phase_index"] = 0
        # Instant funding (fmt["phases"] vide) : pas d'evaluation a repayer,
        # le nouveau compte est de nouveau finance directement (phase reste "funded").
        _reset_trackers(acc)
        return False

    if acc["phase"] == "challenge" and pdef["target_pct"] is not None:
        days_ok = pdef["min_days"] is None or len(acc["trading_days_since_reset"]) >= pdef["min_days"]
        if acc["cumulative_since_reset"] >= pdef["target_pct"] / 100 * acc["palier"] and days_ok:
            just_funded = False
            if acc["phase_index"] + 1 < len(fmt["phases"]):
                acc["phase_index"] += 1
                _reset_trackers(acc)
            else:
                acc["phase"] = "funded"
                if not state.get("ever_funded"):
                    just_funded = True
                state["ever_funded"] = True
                _reset_trackers(acc)
            return just_funded

    return False

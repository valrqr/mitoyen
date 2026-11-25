"""
vente.py — Le dossier de vente en un clic.

Quand un copropriétaire vend, l'acquéreur doit recevoir, annexés à la promesse de
vente (ou à défaut à l'acte authentique), les documents de l'article L. 721-2 du
code de la construction et de l'habitation. Chez un syndic professionnel, ces
documents se paient. Ici, toutes les données sont déjà dans Mitoyen.

Le dossier comprend :
    0. un BORDEREAU : la liste des documents exigés, ce qui est fourni et ce qui
       reste à joindre (règlement de copropriété, procès-verbaux signés…) ;
    1. la FICHE SYNTHÉTIQUE de la copropriété (loi 1965, art. 8-2 ; décret
       n° 2016-1822, art. 2), en six rubriques ;
    2. le PRÉ-ÉTAT DATÉ des lots vendus : charges du budget, échéancier de l'exercice
       en cours, part du fonds de travaux, état global des impayés et des dettes,
       travaux décidés, et ce que le plan de travaux représentera pour ces lots ;
    3. la PROJECTION du plan pluriannuel de travaux ;
    4. les documents déposés par le syndic dans data/<copro>/documents/
       (règlement, procès-verbaux signés, carnet d'entretien, DTG…).

Ce qui ne figure pas dans Mitoyen (les charges réellement payées par le vendeur,
ses éventuels impayés) est fourni par le syndic d'après sa comptabilité, ou signalé
« à compléter ». Rien n'est inventé.

⚠️ Aide à la préparation. L'état daté établi au moment de la vente (décret du
17 mars 1967, art. 5) reste à la charge du syndic, et le notaire vérifie le dossier.
"""

from __future__ import annotations

import json
import re
import zipfile
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path

from fiche_copro import CENT, appel_par_lot, repartir, rubriques

AVERTISSEMENT = ("Document préparé par l'assistant du syndic à partir des données de la copropriété. Il aide à "
                 "réunir les informations exigées par l'article L. 721-2 du code de la construction et de "
                 "l'habitation ; il ne remplace ni l'état daté établi par le syndic lors de la vente, ni les "
                 "vérifications du notaire.")
SEUIL_PETITE_COPRO_LOTS = 10                 # fiche synthétique allégée (décret 2016-1822)
SEUIL_PETITE_COPRO_BUDGET = Decimal("15000")
# Documents que le syndic dépose dans data/<copro>/documents/, reconnus par leur nom
DOCUMENTS = [
    ("reglement", r"^(reglement|edd|etat[-_]descriptif)", "Règlement de copropriété et état descriptif de division"),
    ("pv", r"^pv[-_]", "Procès-verbal d'assemblée générale"),
    ("carnet", r"^carnet", "Carnet d'entretien de l'immeuble"),
    ("dtg", r"^dtg", "Diagnostic technique global"),
    ("notice", r"^notice", "Notice d'information sur les droits et obligations des copropriétaires"),
    ("dpe", r"^dpe", "DPE collectif"),
    ("amiante", r"^(dta|amiante)", "Dossier technique amiante"),
]


class VenteInvalide(ValueError):
    pass


def _d(v) -> Decimal:
    return Decimal(str(v)).quantize(CENT)


def _eur(m) -> str:
    return f"{Decimal(m):,.2f}".replace(",", " ").replace(".", ",") + " €"


# --------------------------------------------------------------------------- #
# 1. Fiche synthétique
# --------------------------------------------------------------------------- #
def fiche_synthetique(fiche: dict, aujourd_hui: date | None = None) -> dict:
    """Les six rubriques du décret n° 2016-1822 (art. 2). Une donnée absente de la
    fiche est signalée, jamais devinée."""
    jour = aujourd_hui or date.today()
    c = fiche["copropriete"]
    gouv = fiche["gouvernance"]
    syndic = next(x for x in fiche["coproprietaires"] if x["id"] == gouv["syndic"]["coproprietaire_id"])
    types = defaultdict(int)
    for l in fiche["lots"]:
        types[l["type"]] += 1
    nb_ascenseurs = sum(1 for e in fiche.get("equipements", []) if e["id"].startswith("ascenseur"))
    budget = sum((Decimal(str(p["montant"])) for p in fiche["budget_previsionnel"]["postes"]), Decimal("0"))
    comptes = fiche.get("comptes_approuves")
    petite = c["nb_lots_total"] < SEUIL_PETITE_COPRO_LOTS and budget < SEUIL_PETITE_COPRO_BUDGET
    manque = "non renseigné dans la fiche"

    def v(x, defaut=manque):
        return defaut if x in (None, "") else x

    rubriques_fs = {
        "Identification de la copropriété": [
            ("Nom d'usage", c["nom"]),
            ("Adresse", c["adresse"]),
            ("N° d'immatriculation au registre national", v(c.get("immatriculation_registre"))),
            ("Date d'établissement du règlement de copropriété",
             f"{c['date_reglement']:%d/%m/%Y}" if isinstance(c.get("date_reglement"), date) else manque),
            ("N° SIRET du syndicat", v(c.get("siret_syndicat"), "sans objet")),
        ],
        "Identité du syndic": [
            ("Représentant légal", f"{syndic['nom']}, syndic {'coopératif' if gouv['mode_gestion'] == 'cooperatif' else 'bénévole'} "
                                   f"(copropriétaire, non professionnel)"),
            ("Adresse", c["adresse"]),
            ("Cadre d'intervention", f"Mandat de syndic du {gouv['syndic']['debut_mandat']:%d/%m/%Y} au "
                                     f"{gouv['syndic']['fin_mandat']:%d/%m/%Y}"),
        ],
        "Organisation juridique": [
            ("Nature du syndicat", "Syndicat coopératif" if gouv["mode_gestion"] == "cooperatif" else "Syndicat principal"),
            ("Résidence-services", "non"),
        ],
        "Caractéristiques techniques": [
            ("Nombre total de lots inscrits au règlement", str(c["nb_lots_total"])),
            ("Lots à usage d'habitation, de commerces et de bureaux",
             f"{types['appartement']} habitation · {types.get('commerce', 0)} commerces · {types.get('bureau', 0)} bureaux"),
            ("Nombre de bâtiments", str(len(c.get("batiments") or [])) if c.get("batiments") else manque),
            ("Période de construction", v(c.get("periode_construction"))),
        ],
        "Équipements": [
            ("Type de chauffage", v(c.get("chauffage"))
             + (f" ({c['energie_chauffage_collectif']})" if c.get("energie_chauffage_collectif") else "")),
            ("Nombre d'ascenseurs", str(nb_ascenseurs)),
        ],
    }
    fin = [("Personnel employé par le syndicat",
            "oui" if c.get("personnel_employe") else "non" if c.get("personnel_employe") is False else manque)]
    if comptes:
        fin += [
            ("Dernier exercice clos et approuvé", f"du {comptes['debut']:%d/%m/%Y} au {comptes['fin']:%d/%m/%Y}, "
                                                 f"approuvé en AG le {comptes['ag_approbation']:%d/%m/%Y}"),
            ("Charges courantes (budget prévisionnel)", _eur(comptes["charges_courantes"])),
            ("Charges de travaux et opérations exceptionnelles", _eur(comptes["charges_travaux_exceptionnelles"])),
            ("Dettes fournisseurs, rémunérations et autres", _eur(comptes["dettes_fournisseurs"])),
        ]
        if not petite:
            fin += [("Impayés de charges", _eur(comptes["impayes"])),
                    ("Copropriétaires débiteurs de plus de 300 €", str(comptes["nb_debiteurs_plus_300"]))]
        fin.append(("Fonds de travaux à la clôture", _eur(comptes["fonds_travaux"])))
    else:
        fin.append(("Comptes du dernier exercice approuvé", manque + " (section comptes_approuves)"))
    rubriques_fs["Caractéristiques financières"] = fin
    manquants = [f"{r} : {lib}" for r, lignes in rubriques_fs.items() for lib, val in lignes
                 if isinstance(val, str) and manque in val]
    return {"etablie_le": jour.isoformat(), "rubriques": rubriques_fs, "manquants": manquants,
            "allegee": petite}


# --------------------------------------------------------------------------- #
# 2. Pré-état daté des lots vendus
# --------------------------------------------------------------------------- #
def lots_vendus(fiche: dict, numeros: list[int]) -> tuple[str, list[dict]]:
    if not numeros:
        raise VenteInvalide("Indiquer au moins un lot vendu")
    par_num = {l["numero"]: l for l in fiche["lots"]}
    inconnus = [n for n in numeros if n not in par_num]
    if inconnus:
        raise VenteInvalide(f"Lot(s) inconnu(s) : {', '.join(map(str, inconnus))}")
    proprios = {par_num[n]["proprietaire"] for n in numeros}
    if len(proprios) > 1:
        raise VenteInvalide("Les lots vendus appartiennent à plusieurs copropriétaires : un dossier par vendeur")
    return proprios.pop(), [par_num[n] for n in sorted(set(numeros))]


def _part_lots(fiche: dict, numeros: set[int], montant: Decimal, cle: str) -> Decimal:
    """Part exacte des lots dans un montant réparti lot par lot selon une clé."""
    poids = {l["numero"]: l["tantiemes"].get(cle, 0) for l in fiche["lots"] if l["tantiemes"].get(cle, 0) > 0}
    if not poids or montant == 0:
        return Decimal("0.00")
    return sum((m for n, m in repartir(montant, poids).items() if n in numeros), Decimal("0.00"))


def pre_etat_date(fiche: dict, numeros: list[int], racine: Path | None = None, copro: str | None = None,
                  comptes_vendeur: dict | None = None, aujourd_hui: date | None = None) -> dict:
    jour = aujourd_hui or date.today()
    cid, lots = lots_vendus(fiche, numeros)
    nums = {l["numero"] for l in lots}
    vendeur = next(x for x in fiche["coproprietaires"] if x["id"] == cid)
    cles = fiche["cles_repartition"]
    adf = fiche["appels_de_fonds"]
    exercice = fiche["budget_previsionnel"]["exercice"]
    cv = comptes_vendeur or {}

    # Quote-part annuelle des lots, rubrique par rubrique (comme sur les avis d'appel)
    par_lot = appel_par_lot(fiche)
    nb_appels = len(adf["dates_exigibilite"])
    annuel = []
    for rub in rubriques(fiche):
        appel = sum((m for (rid, n), m in par_lot.items() if rid == rub["id"] and n in nums), Decimal("0"))
        if appel:
            annuel.append({"libelle": rub["libelle"], "cle": rub["cle"], "par_appel": appel, "annuel": appel * nb_appels})
    par_appel = sum((r["par_appel"] for r in annuel), Decimal("0"))
    echeancier = []
    for mmjj in adf["dates_exigibilite"]:
        mm, jj = (int(x) for x in mmjj.split("-"))
        d = date(exercice, mm, jj)
        echeancier.append({"date": d.isoformat(), "date_fr": f"{d:%d/%m/%Y}", "montant": par_appel,
                           "statut": "échu" if d <= jour else "à échoir"})

    # Fonds de travaux : part rattachée aux lots (elle reste acquise au syndicat)
    ft = fiche["fonds_travaux"]
    base = cles[ft["cle"]]["base"]
    tant_ft = sum(l["tantiemes"].get(ft["cle"], 0) for l in lots)
    solde = (fiche["fonds_travaux"].get("solde") or {})
    fonds = {
        "tantiemes": f"{tant_ft} / {base}",
        "solde_syndicat": _d(solde["montant"]) if solde else None,
        "solde_au": f"{solde['au']:%d/%m/%Y}" if solde else None,
        "part_lots": _part_lots(fiche, nums, _d(solde["montant"]), ft["cle"]) if solde else None,
        "derniere_cotisation_annuelle": _part_lots(fiche, nums, _d(ft["cotisation_annuelle"]), ft["cle"]),
    }

    # Travaux décidés en AG et rattachés à un dossier : part des lots
    travaux_votes = []
    if racine and copro:
        import ag as assemblee
        import travaux
        for a in assemblee.lister_ag(racine, copro):
            if not a["depouillee"]:
                continue
            ag_data = assemblee.charger_ag(racine, copro, a["id"])
            dep = assemblee.depouiller(fiche, ag_data, ag_data["depouillement"]["votes"],
                                       ag_data["depouillement"]["amendees"])
            for r in dep["resolutions"]:
                res_src = next(x for x in ag_data["resolutions"] if x["num"] == r["num"])
                if not (r["adoptee"] and res_src.get("dossier") and r.get("retenue", True)):
                    continue
                try:
                    d = travaux.charger_dossier(travaux.dossier_dir(racine, copro, res_src["dossier"]))
                except FileNotFoundError:
                    continue
                m = re.search(r"devis (D\d+)", r["titre"])
                devis = next((x for x in d["devis"] if m and x["id"] == m.group(1)), None)
                if devis:
                    ttc = travaux.montant_ttc(devis)
                    travaux_votes.append({"ag": a["date"], "titre": d["titre"], "montant_ttc": ttc,
                                          "part_lots": _part_lots(fiche, nums, ttc, d["cle"])})

    # Plan de travaux : ce que les lots paieront, année par année
    plan = None
    if fiche.get("plan_travaux"):
        import plan_travaux
        suivi = plan_travaux.charger_suivi(racine, copro) if racine and copro else {}
        proj = plan_travaux.projection(fiche, suivi)
        annees = []
        for a in proj["annees"]:
            cot = _part_lots(fiche, nums, a["cotisation"], ft["cle"])
            appels_par_cle: dict[str, Decimal] = defaultdict(Decimal)
            for t in a["travaux"]:
                appels_par_cle[t["cle"]] += t["appel_complementaire"]
            app = sum((_part_lots(fiche, nums, m, k) for k, m in appels_par_cle.items() if m > 0), Decimal("0"))
            annees.append({"annee": a["annee"], "cotisation": cot, "appels": app, "total": cot + app,
                           "travaux": ", ".join(t["intitule"] for t in a["travaux"])})
        plan = {"statut": fiche["plan_travaux"]["statut"], "annees": annees,
                "total": sum((x["total"] for x in annees), Decimal("0"))}

    comptes = fiche.get("comptes_approuves") or {}
    a_completer = []
    charges_payees = cv.get("charges_payees") or []
    if len(charges_payees) < 2:
        a_completer.append("Charges courantes et hors budget payées par le vendeur sur les deux derniers exercices")
    if cv.get("impayes_vendeur") is None:
        a_completer.append("Sommes restant dues par le vendeur au syndicat (impayés)")
    if cv.get("etat_global"):
        comptes = cv["etat_global"]          # tiré de la comptabilité tenue dans Mitoyen
    if not comptes:
        a_completer.append("État global des impayés et des dettes fournisseurs (comptes du dernier exercice approuvé)")
    return {
        "vendeur": {"id": cid, "nom": vendeur["nom"]},
        "lots": [{"numero": l["numero"], "type": l["type"], "desc": l.get("desc", ""),
                  "tantiemes": {k: l["tantiemes"].get(k, 0) for k in cles}} for l in lots],
        "exercice": exercice, "budget_annuel_lots": annuel,
        "total_annuel_lots": sum((r["annuel"] for r in annuel), Decimal("0")),
        "echeancier": echeancier, "fonds_travaux": fonds,
        "charges_payees": [{"exercice": int(x["exercice"]), "budget": _d(x.get("budget", 0)),
                            "hors_budget": _d(x.get("hors_budget", 0))} for x in charges_payees],
        "impayes_vendeur": _d(cv["impayes_vendeur"]) if cv.get("impayes_vendeur") is not None else None,
        "etat_global": {"exercice": comptes.get("exercice"), "impayes": comptes.get("impayes"),
                        "dettes_fournisseurs": comptes.get("dettes_fournisseurs")} if comptes else None,
        "travaux_votes": travaux_votes, "plan": plan, "a_completer": a_completer,
        "etabli_le": jour.isoformat(), "avertissement": AVERTISSEMENT,
    }


# --------------------------------------------------------------------------- #
# 3. Bordereau (art. L. 721-2 du CCH) et documents déposés par le syndic
# --------------------------------------------------------------------------- #
def documents_deposes(racine: Path | None, copro: str | None) -> dict[str, list[Path]]:
    res: dict[str, list[Path]] = defaultdict(list)
    if not (racine and copro):
        return res
    dossier = Path(racine) / copro / "documents"
    if not dossier.is_dir():
        return res
    for f in sorted(dossier.iterdir()):
        if f.is_file() and f.suffix.lower() == ".pdf":
            for cle, motif, _ in DOCUMENTS:
                if re.match(motif, f.name.lower()):
                    res[cle].append(f)
                    break
    return res


def bordereau(fiche: dict, pre: dict, docs: dict[str, list[Path]], racine: Path | None = None,
              copro: str | None = None, acquereur_coproprietaire: bool = False) -> list[dict]:
    """Chaque document exigé : fourni par Mitoyen, déposé par le syndic, ou à joindre."""
    ags = []
    if racine and copro:
        import ag as assemblee
        ags = [a for a in assemblee.lister_ag(racine, copro) if a["depouillee"]]
    pvs = [f.name for f in docs.get("pv", [])]

    def deposes(cle, sinon):
        return ("depose", ", ".join(f.name for f in docs[cle])) if docs.get(cle) else sinon

    items = [
        ("1° a", "Fiche synthétique de la copropriété", ("fourni", "01_fiche_synthetique.pdf")),
        ("1° b", "Règlement de copropriété et état descriptif de division, avec leurs modificatifs",
         deposes("reglement", ("a_joindre", "à demander au syndic ou au notaire (publiés au service de la publicité foncière)"))),
        ("1° c", "Procès-verbaux des assemblées générales des trois dernières années",
         ("depose", ", ".join(pvs)) if pvs else
         ("a_joindre", "PV signés à joindre" + (f" (AG tenues avec Mitoyen : {', '.join(a['date'] for a in ags)})" if ags else ""))),
        ("2° a", "Charges courantes et hors budget payées par le vendeur sur les deux derniers exercices",
         ("fourni", "02_pre_etat_date.pdf") if len(pre["charges_payees"]) >= 2 else ("a_completer", "d'après la comptabilité du syndic")),
        ("2° b", "Sommes susceptibles d'être dues au syndicat par l'acquéreur", ("fourni", "02_pre_etat_date.pdf")),
        ("2° c", "État global des impayés de charges et de la dette envers les fournisseurs",
         ("fourni", "02_pre_etat_date.pdf") if pre["etat_global"] else ("a_completer", "comptes du dernier exercice approuvé")),
        ("2° d", "Part du fonds de travaux rattachée aux lots et dernière cotisation versée", ("fourni", "02_pre_etat_date.pdf")),
        ("3°", "Carnet d'entretien de l'immeuble", deposes("carnet", ("a_joindre", "à joindre par le syndic"))),
        ("4°", "Notice d'information sur les droits et obligations des copropriétaires",
         deposes("notice", ("a_joindre", "modèle officiel publié par arrêté, disponible sur Légifrance"))),
        ("5°", "Diagnostic technique global et plan pluriannuel de travaux",
         ("fourni", "03_plan_travaux.pdf" + (" + " + ", ".join(f.name for f in docs["dtg"]) if docs.get("dtg") else
                                             " (pas de DTG réalisé)")) if fiche.get("plan_travaux") else
         deposes("dtg", ("a_joindre", "le cas échéant"))),
    ]
    # Acquéreur déjà copropriétaire : il dispose déjà de l'organisation de l'immeuble
    deja = {"1° a", "1° b", "1° c", "3°", "4°", "5°"} if acquereur_coproprietaire else set()
    return [{"ref": r, "document": doc, "etat": "deja_detenu" if r in deja else etat, "detail":
             "l'acquéreur, déjà copropriétaire, le détient" if r in deja else detail}
            for r, doc, (etat, detail) in items]


# --------------------------------------------------------------------------- #
# 4. PDF et archive
# --------------------------------------------------------------------------- #
def _doc(chemin: Path, titre: str):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate
    return SimpleDocTemplate(str(chemin), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                             topMargin=20 * mm, bottomMargin=18 * mm, title=titre)


def generer_fiche_synthetique(fiche: dict, chemin: Path, aujourd_hui: date | None = None) -> Path:
    from reportlab.lib.units import mm
    from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table, TableStyle

    from avis_appel import FILET, GRIS, S, tampon, CanevasNumerote
    fs = fiche_synthetique(fiche, aujourd_hui)
    c = fiche["copropriete"]
    h = [Paragraph("Fiche synthétique de la copropriété", S["titre"]),
         Paragraph(f"{c['nom']} · établie le {date.fromisoformat(fs['etablie_le']):%d/%m/%Y} · décret n° 2016-1822",
                   S["sous"]), Spacer(1, 4 * mm)]
    from reportlab.lib.styles import ParagraphStyle
    cel = ParagraphStyle("cel", parent=S["txt"], leading=12)
    for i, (rub, lignes) in enumerate(fs["rubriques"].items(), 1):
        t = Table([[Paragraph(lib, cel), Paragraph(str(val), cel)] for lib, val in lignes],
                  colWidths=[74 * mm, 100 * mm])
        t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.3, FILET), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("TEXTCOLOR", (0, 0), (0, -1), GRIS), ("TOPPADDING", (0, 0), (-1, -1), 2),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
        h += [KeepTogether([Paragraph(f"{i}. {rub}", S["sous"]), Spacer(1, 1 * mm), t]), Spacer(1, 3 * mm)]
    if fs["allegee"]:
        h.append(Paragraph("Copropriété de moins de 10 lots au budget inférieur à 15 000 € : le nombre de débiteurs "
                           "et le montant des impayés ne figurent pas sur la fiche.", S["petit"]))
    h += [Spacer(1, 2 * mm), Paragraph("La fiche est mise à jour chaque année, dans les deux mois qui suivent la "
                                       "notification du procès-verbal de l'AG qui a approuvé les comptes.", S["petit"])]
    pied = f"{c['nom']} – fiche synthétique"
    _doc(chemin, "Fiche synthétique").build(h, canvasmaker=CanevasNumerote, onFirstPage=tampon(False, pied), onLaterPages=tampon(False, pied))
    return chemin


def generer_pre_etat_date(fiche: dict, pre: dict, chemin: Path) -> Path:
    from reportlab.lib.units import mm
    from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table, TableStyle

    from avis_appel import ACCENT, FOND, S, essentiel, euros, tableau, tampon, CanevasNumerote
    c = fiche["copropriete"]
    lots_txt = ", ".join(f"lot {l['numero']} ({l['desc'] or l['type']})" for l in pre["lots"])
    jour = date.fromisoformat(pre["etabli_le"])
    h = [Paragraph("Pré-état daté", S["titre"]),
         Paragraph(f"{c['nom']} · vendeur : {pre['vendeur']['nom']} · {lots_txt} · établi le {jour:%d/%m/%Y}", S["sous"]),
         Spacer(1, 5 * mm)]
    nb_appels = len(pre["echeancier"]) or 1
    chiffres = [(f"Charges {pre['exercice']}", euros(pre["total_annuel_lots"]),
                 f"budget voté, soit {euros(pre['total_annuel_lots'] / nb_appels)} par appel")]
    if pre["fonds_travaux"]["part_lots"] is not None:
        chiffres.append(("Fonds de travaux", euros(pre["fonds_travaux"]["part_lots"]),
                         "part des lots, acquise au syndicat"))
    if pre["plan"]:
        lourde = max(pre["plan"]["annees"], key=lambda a: a["total"])
        chiffres.append(("Plan de travaux", euros(pre["plan"]["total"]),
                         f"sur 10 ans, dont {euros(lourde['total'])} en {lourde['annee']}"))
    du = pre["impayes_vendeur"]
    chiffres.append(("Dû par le vendeur", "à compléter" if du is None else "aucune somme" if du == 0 else euros(du),
                     "d'après la comptabilité du syndic"))
    h += [essentiel(chiffres), Spacer(1, 6 * mm)]
    if pre["a_completer"]:
        txt = "<b>À compléter par le syndic</b>, d'après sa comptabilité :<br/>" + "<br/>".join(f"• {x}" for x in pre["a_completer"])
        t = Table([[Paragraph(txt, S["txt"])]], colWidths=[174 * mm])
        t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, ACCENT), ("LEFTPADDING", (0, 0), (-1, -1), 8),
                               ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
        h += [t, Spacer(1, 5 * mm)]

    # A. Budget et échéancier
    lignes = [["Rubrique", "Par appel", f"Annuel {pre['exercice']}"]]
    lignes += [[r["libelle"], euros(r["par_appel"]), euros(r["annuel"])] for r in pre["budget_annuel_lots"]]
    lignes.append(["Total", euros(sum((r["par_appel"] for r in pre["budget_annuel_lots"]), Decimal("0"))),
                   euros(pre["total_annuel_lots"])])
    ech = [["Échéance", "Montant", "Situation"]] + [[e["date_fr"], euros(e["montant"]), e["statut"]] for e in pre["echeancier"]]
    h += [Paragraph("A. Charges des lots vendus (budget prévisionnel voté)", S["sous"]), Spacer(1, 2 * mm),
          tableau(lignes, [104 * mm, 34 * mm, 36 * mm], aligner_droite_depuis=1), Spacer(1, 3 * mm),
          tableau(ech, [60 * mm, 50 * mm, 64 * mm], aligner_droite_depuis=1, lignes_total=0), Spacer(1, 2 * mm),
          Paragraph("La répartition entre vendeur et acquéreur des appels de l'exercice en cours se règle dans l'acte "
                    "de vente ; à défaut, chaque appel est dû par celui qui est copropriétaire à sa date d'exigibilité.",
                    S["petit"]), Spacer(1, 5 * mm)]

    # B. Charges payées par le vendeur
    if pre["charges_payees"]:
        cp = [["Exercice", "Charges courantes", "Hors budget"]] + [
            [str(x["exercice"]), euros(x["budget"]), euros(x["hors_budget"])] for x in pre["charges_payees"]]
        bloc_b = tableau(cp, [60 * mm, 57 * mm, 57 * mm], aligner_droite_depuis=1, lignes_total=0)
    else:
        bloc_b = Paragraph("À compléter d'après la comptabilité du syndic.", S["txt"])
    imp = ("aucune" if pre["impayes_vendeur"] == 0 else euros(pre["impayes_vendeur"])) if pre["impayes_vendeur"] is not None \
        else "à compléter"
    h += [KeepTogether([Paragraph("B. Charges payées par le vendeur sur les deux derniers exercices", S["sous"]),
                        Spacer(1, 2 * mm), bloc_b, Spacer(1, 2 * mm),
                        Paragraph(f"Sommes restant dues par le vendeur au syndicat : <b>{imp}</b>", S["txt"])]),
          Spacer(1, 5 * mm)]

    # C. Fonds de travaux et état global
    f = pre["fonds_travaux"]
    eg = pre["etat_global"]
    txt_c = (f"Part du fonds de travaux rattachée aux lots ({f['tantiemes']}) : <b>{euros(f['part_lots'])}</b> "
             f"sur un fonds de {euros(f['solde_syndicat'])} au {f['solde_au']}. Cette part reste acquise au syndicat : "
             f"elle n'est pas remboursée au vendeur.<br/>"
             if f["part_lots"] is not None else "Solde du fonds de travaux : à compléter.<br/>")
    txt_c += f"Cotisation annuelle au fonds de travaux pour ces lots : <b>{euros(f['derniere_cotisation_annuelle'])}</b>."
    if eg:
        txt_c += (f"<br/>État global du syndicat à la clôture de l'exercice {eg['exercice']} : impayés de charges "
                  f"{euros(Decimal(str(eg['impayes'])))} ; dettes envers les fournisseurs "
                  f"{euros(Decimal(str(eg['dettes_fournisseurs'])))}.")
    h += [KeepTogether([Paragraph("C. Fonds de travaux et situation financière du syndicat", S["sous"]),
                        Spacer(1, 2 * mm), Paragraph(txt_c, S["txt"])]), Spacer(1, 5 * mm)]

    # D. Travaux décidés
    if pre["travaux_votes"]:
        tv = [["AG", "Travaux", "Total TTC", "Part des lots"]] + [
            [date.fromisoformat(t["ag"]).strftime("%d/%m/%Y"), Paragraph(t["titre"], S["txt"]), euros(t["montant_ttc"]),
             euros(t["part_lots"])] for t in pre["travaux_votes"]]
        bloc_d = tableau(tv, [24 * mm, 90 * mm, 30 * mm, 30 * mm], aligner_droite_depuis=2, lignes_total=0)
    else:
        bloc_d = Paragraph("Aucun travaux décidé en AG en attente d'appel, d'après les données de Mitoyen.", S["txt"])
    h += [KeepTogether([Paragraph("D. Travaux décidés en assemblée générale", S["sous"]), Spacer(1, 2 * mm), bloc_d]),
          Spacer(1, 5 * mm)]

    # E. Plan de travaux
    if pre["plan"]:
        p = pre["plan"]
        tp = [["Année", "Cotisation fonds", "Appels en plus", "Total", "Travaux prévus"]] + [
            [str(a["annee"]), euros(a["cotisation"]), euros(a["appels"]) if a["appels"] else "—", euros(a["total"]),
             Paragraph(a["travaux"] or "—", S["petit"])] for a in p["annees"]]
        tp.append(["Total", "", "", euros(p["total"]), ""])
        statut = "adopté en AG" if p["statut"] == "adopte" else "projet, pas encore adopté"
        tab_plan = tableau(tp, [16 * mm, 30 * mm, 28 * mm, 28 * mm, 72 * mm], aligner_droite_depuis=1)
        tab_plan.setStyle(TableStyle([("ALIGN", (4, 0), (4, -1), "LEFT")]))
        h += [Paragraph(f"E. Ce que le plan pluriannuel de travaux représente pour ces lots ({statut})", S["sous"]),
              Spacer(1, 2 * mm), tab_plan,
              Spacer(1, 2 * mm),
              Paragraph("Projection indicative, avec la cotisation actuelle au fonds de travaux et les estimations du "
                        "plan. Détail complet dans le document « 03_plan_travaux.pdf ».", S["petit"]), Spacer(1, 5 * mm)]
    h += [Paragraph(AVERTISSEMENT, S["petit"])]
    pied = f"{c['nom']} – pré-état daté – {pre['vendeur']['nom']}"
    _doc(chemin, "Pré-état daté").build(h, canvasmaker=CanevasNumerote, onFirstPage=tampon(False, pied), onLaterPages=tampon(False, pied))
    return chemin


def generer_bordereau(fiche: dict, pre: dict, items: list[dict], chemin: Path) -> Path:
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Spacer

    from avis_appel import S, tableau, tampon, CanevasNumerote
    c = fiche["copropriete"]
    etats = {"fourni": "Fourni", "depose": "Joint", "a_joindre": "À joindre", "a_completer": "À compléter",
             "deja_detenu": "Déjà détenu"}
    lots_txt = ", ".join(str(l["numero"]) for l in pre["lots"])
    lignes = [["", "Document exigé", "État", "Fichier ou démarche"]] + [
        [i["ref"], Paragraph(i["document"], S["txt"]), etats[i["etat"]], Paragraph(i["detail"], S["petit"])]
        for i in items]
    nb_ok = sum(1 for i in items if i["etat"] in ("fourni", "depose", "deja_detenu"))
    h = [Paragraph("Dossier de vente — bordereau", S["titre"]),
         Paragraph(f"{c['nom']} · vendeur : {pre['vendeur']['nom']} · lot(s) {lots_txt} · "
                   f"{date.fromisoformat(pre['etabli_le']):%d/%m/%Y}", S["sous"]), Spacer(1, 5 * mm),
         Paragraph(f"Documents à annexer à la promesse de vente (code de la construction et de l'habitation, "
                   f"art. L. 721-2) : <b>{nb_ok} sur {len(items)}</b> réunis dans ce dossier.", S["txt"]),
         Spacer(1, 4 * mm),
         tableau(lignes, [12 * mm, 70 * mm, 24 * mm, 68 * mm], aligner_droite_depuis=4, lignes_total=0),
         Spacer(1, 4 * mm),
         Paragraph("Tant que ces documents ne sont pas remis à l'acquéreur, son délai de rétractation ne commence pas "
                   "à courir. Les diagnostics techniques du logement (DPE, électricité, amiante…) relèvent du vendeur "
                   "et ne figurent pas dans ce dossier.", S["petit"]),
         Spacer(1, 3 * mm), Paragraph(AVERTISSEMENT, S["petit"])]
    pied = f"{c['nom']} – dossier de vente – {pre['vendeur']['nom']}"
    _doc(chemin, "Dossier de vente").build(h, canvasmaker=CanevasNumerote, onFirstPage=tampon(False, pied), onLaterPages=tampon(False, pied))
    return chemin


def generer_dossier(fiche: dict, numeros: list[int], sortie: Path, racine: Path | None = None,
                    copro: str | None = None, comptes_vendeur: dict | None = None,
                    acquereur_coproprietaire: bool = False, aujourd_hui: date | None = None) -> dict:
    """Produit les PDF et l'archive ZIP du dossier de vente."""
    import plan_travaux
    jour = aujourd_hui or date.today()
    pre = pre_etat_date(fiche, numeros, racine, copro, comptes_vendeur, jour)
    docs = documents_deposes(racine, copro)
    items = bordereau(fiche, pre, docs, racine, copro, acquereur_coproprietaire)
    vid = f"{jour:%Y%m%d}-lots-{'-'.join(str(l['numero']) for l in pre['lots'])}"
    dossier = Path(sortie) / vid
    dossier.mkdir(parents=True, exist_ok=True)
    fichiers = [generer_bordereau(fiche, pre, items, dossier / "00_bordereau.pdf"),
                generer_fiche_synthetique(fiche, dossier / "01_fiche_synthetique.pdf", jour),
                generer_pre_etat_date(fiche, pre, dossier / "02_pre_etat_date.pdf")]
    if fiche.get("plan_travaux"):
        suivi = plan_travaux.charger_suivi(racine, copro) if racine and copro else {}
        fichiers.append(plan_travaux.generer_pdf(fiche, dossier / "03_plan_travaux.pdf", suivi, aujourd_hui=jour))
    archive = dossier / f"dossier_vente_{vid}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for f in fichiers:
            z.write(f, f.name)
        for liste in docs.values():
            for f in liste:
                z.write(f, f"documents/{f.name}")
    resume = {"id": vid, "vendeur": pre["vendeur"], "lots": [l["numero"] for l in pre["lots"]],
              "bordereau": items, "a_completer": pre["a_completer"],
              "fichiers": [f.name for f in fichiers], "documents_joints": sorted(f.name for l in docs.values() for f in l),
              "archive": archive.name}
    (dossier / "dossier.json").write_text(json.dumps(resume, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return {**resume, "chemin_archive": str(archive)}

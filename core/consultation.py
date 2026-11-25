"""
consultation.py — Le régime des petites copropriétés : décider sans réunir d'assemblée générale.

Loi du 10 juillet 1965, art. 41-8 et suivants ; décret du 17 mars 1967, art. 42-3 à 42-5.

Une petite copropriété compte au plus cinq lots à usage de logements, de bureaux ou de
commerces, ou a un budget prévisionnel moyen inférieur à 15 000 € sur trois exercices
consécutifs. Ses décisions peuvent être prises par CONSULTATION des copropriétaires, à
l'UNANIMITÉ, sans convoquer d'assemblée générale, sauf le vote du budget prévisionnel et
l'approbation des comptes (une AG par an reste donc nécessaire).

Ce que le décret impose, et que ce module applique :
    - la décision n'est valable que si TOUS les copropriétaires ont exprimé leur vote : en
      personne (ou par délégation), par visioconférence si l'AG l'a admis, ou par courrier,
      papier ou électronique (art. 42-3) ;
    - quand un copropriétaire la demande, le syndic organise la consultation dans les
      21 jours (art. 42-4) ;
    - chaque décision est consignée sur un procès-verbal établi et signé par le syndic, avec le
      sens du vote de chacun ; les écrits des votes y sont annexés, et le tout rejoint le
      registre des procès-verbaux d'AG (art. 42-5).
Et la loi (art. 41-12) : lorsqu'un copropriétaire a été consulté par écrit, la décision est
formalisée AU TERME DU DÉLAI fixé par le syndic pour répondre, même si tous ont déjà voté pour.

Unanimité : un seul « contre », une abstention ou une absence de réponse, et la décision
n'est pas prise ; la question peut alors être portée à l'ordre du jour d'une AG.

⚠️ Aide à l'organisation, pas un conseil juridique. L'ADIL renseigne gratuitement.
"""

from __future__ import annotations

import json
import re
import secrets
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from vote import hacher

SEUIL_LOTS = 5
SEUIL_BUDGET = Decimal("15000")
TYPES_PRINCIPAUX_EXCLUS = {"cave", "parking", "box", "garage", "cellier", "local_velos"}
DELAI_ORGANISATION_JOURS = 21               # décret 1967, art. 42-4
CHOIX = {"pour": "Pour", "contre": "Contre", "abstention": "Abstention"}
ECRIT = {"lien", "courrier", "electronique"}     # consultation écrite : formalisée au terme du délai
MODES = {"lien": "par voie électronique (lien personnel)", "courrier": "par courrier papier",
         "electronique": "par courrier électronique", "presence": "en personne",
         "delegation": "par délégation de vote", "visio": "par visioconférence ou audioconférence"}
EXCLUS = re.compile(r"\b(budget\s+pr[ée]visionnel|approbation\s+des\s+comptes|approuver\s+les\s+comptes)\b", re.I)
AVERTISSEMENT = ("Consultation organisée avec Mitoyen selon le régime des petites copropriétés (loi du 10 juillet "
                 "1965, art. 41-8 et suivants ; décret du 17 mars 1967, art. 42-3 à 42-5). Ce n'est pas un conseil "
                 "juridique : l'ADIL de votre département répond gratuitement.")


class ConsultationInvalide(ValueError):
    pass


# --------------------------------------------------------------------------- #
# Le régime s'applique-t-il ?
# --------------------------------------------------------------------------- #
def lots_principaux(fiche: dict) -> list[dict]:
    return [l for l in fiche["lots"] if l.get("type") not in TYPES_PRINCIPAUX_EXCLUS]


def regime(fiche: dict, budgets: dict[int, list] | None = None) -> dict:
    """Le régime des petites copropriétés s'applique-t-il, et à quel titre ?"""
    n = len(lots_principaux(fiche))
    par_an = {}
    for ex, postes in (budgets or {}).items():
        par_an[int(ex)] = sum((Decimal(str(p["montant"])) for p in postes), Decimal("0"))
    bp = fiche.get("budget_previsionnel") or {}
    if bp.get("exercice") and int(bp["exercice"]) not in par_an:
        par_an[int(bp["exercice"])] = sum((Decimal(str(p["montant"])) for p in bp.get("postes", [])), Decimal("0"))
    moyenne, exercices = None, None
    for fin in sorted(par_an, reverse=True):
        serie = [fin - 2, fin - 1, fin]
        if all(x in par_an for x in serie):
            moyenne = (sum(par_an[x] for x in serie) / 3).quantize(Decimal("0.01"))
            exercices = serie
            break
    par_lots = n <= SEUIL_LOTS
    par_budget = moyenne is not None and moyenne < SEUIL_BUDGET
    motifs = []
    if par_lots:
        motifs.append(f"{n} lot{'s' if n > 1 else ''} à usage de logements, de bureaux ou de commerces (5 au plus)")
    if par_budget:
        motifs.append(f"budget prévisionnel moyen de {moyenne} € sur {exercices[0]}-{exercices[-1]} (moins de 15 000 €)")
    return {"applicable": par_lots or par_budget, "lots_principaux": n, "budget_moyen": moyenne,
            "exercices": exercices, "motifs": motifs,
            "detail": "La copropriété relève du régime des petites copropriétés : " + " ; ".join(motifs) + "."
            if motifs else
            f"La copropriété compte {n} lots principaux"
            + (f" et un budget moyen de {moyenne} €" if moyenne is not None else
               " ; le budget moyen sur trois exercices n'est pas connu")
            + " : le régime des petites copropriétés ne s'applique pas."}


# --------------------------------------------------------------------------- #
# Stockage
# --------------------------------------------------------------------------- #
def _dossier(racine: Path, copro: str) -> Path:
    return Path(racine) / copro / "consultations"


def charger(racine: Path, copro: str, cid: str) -> dict:
    if not re.fullmatch(r"C\d{3}", cid or ""):
        raise ConsultationInvalide("Consultation inconnue")
    f = _dossier(racine, copro) / f"{cid}.json"
    if not f.is_file():
        raise ConsultationInvalide("Consultation inconnue")
    return json.loads(f.read_text(encoding="utf-8"))


def sauver(racine: Path, copro: str, c: dict) -> None:
    d = _dossier(racine, copro)
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / f"{c['id']}.tmp"
    tmp.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(d / f"{c['id']}.json")


def lister(racine: Path, copro: str) -> list[dict]:
    d = _dossier(racine, copro)
    if not d.is_dir():
        return []
    return [json.loads(f.read_text(encoding="utf-8")) for f in sorted(d.glob("C*.json"), reverse=True)]


# --------------------------------------------------------------------------- #
# Ouvrir, voter, conclure
# --------------------------------------------------------------------------- #
def ouvrir(racine: Path, copro: str, fiche: dict, titre: str, resolution: str, repondre_avant: date,
           budgets: dict | None = None, demandee_par: str | None = None, demandee_le: date | None = None,
           maintenant: datetime | None = None) -> tuple[dict, dict[str, str]]:
    """Ouvre une consultation. Renvoie (consultation, {copropriétaire: jeton en clair}) ;
    les jetons en clair ne sont jamais stockés, seule leur empreinte l'est."""
    r = regime(fiche, budgets)
    if not r["applicable"]:
        raise ConsultationInvalide(r["detail"] + " Les décisions se prennent en assemblée générale.")
    titre, resolution = (titre or "").strip()[:160], (resolution or "").strip()[:4000]
    if not titre or not resolution:
        raise ConsultationInvalide("Indiquer la question et le texte de la décision proposée")
    if EXCLUS.search(titre + " " + resolution):
        raise ConsultationInvalide("Le budget prévisionnel et l'approbation des comptes se votent en assemblée "
                                   "générale, pas par consultation")
    maintenant = (maintenant or datetime.now()).replace(microsecond=0)
    if repondre_avant <= maintenant.date():
        raise ConsultationInvalide("La date limite de réponse doit être à venir")
    copros = {c["id"]: c for c in fiche["coproprietaires"]}
    if demandee_par and demandee_par not in copros:
        raise ConsultationInvalide("Copropriétaire demandeur inconnu")
    existantes = lister(racine, copro)
    numero = max((int(c["id"][1:]) for c in existantes), default=0) + 1
    # tous les copropriétaires qui ont au moins un lot : l'unanimité porte sur eux tous
    electeurs = sorted({l["proprietaire"] for l in fiche["lots"]})
    jetons = {e: secrets.token_urlsafe(18) for e in electeurs}
    c = {"id": f"C{numero:03d}", "titre": titre, "resolution": resolution, "ouverte_le": maintenant.isoformat(),
         "repondre_avant": repondre_avant.isoformat(), "close_le": None,
         "demande": {"par": demandee_par, "le": (demandee_le or maintenant.date()).isoformat()} if demandee_par else None,
         "electeurs": {e: {"jeton": hacher(j), "choix": None, "le": None, "mode": None, "piece": None}
                       for e, j in jetons.items()}}
    sauver(racine, copro, c)
    return c, jetons


def renouveler_jeton(racine: Path, copro: str, cid: str, electeur: str) -> str:
    c = charger(racine, copro, cid)
    if electeur not in c["electeurs"]:
        raise ConsultationInvalide("Copropriétaire inconnu")
    j = secrets.token_urlsafe(18)
    c["electeurs"][electeur]["jeton"] = hacher(j)
    sauver(racine, copro, c)
    return j


def trouver(c: dict, jeton: str) -> str | None:
    h = hacher(jeton or "")
    return next((e for e, v in c["electeurs"].items() if secrets.compare_digest(v["jeton"], h)), None)


def ouverte(c: dict, maintenant: datetime | None = None) -> bool:
    jour = (maintenant or datetime.now()).date().isoformat()
    return not c.get("close_le") and jour <= c["repondre_avant"]


def voter(c: dict, electeur: str, choix: str, mode: str, piece: str | None = None,
          maintenant: datetime | None = None) -> dict:
    """Enregistre le vote d'un copropriétaire. Un vote exprimé ne se modifie pas : chacun vote une fois."""
    if not ouverte(c, maintenant):
        raise ConsultationInvalide("La consultation est close")
    if choix not in CHOIX:
        raise ConsultationInvalide("Choix invalide")
    if mode not in MODES:
        raise ConsultationInvalide("Mode de vote inconnu")
    e = c["electeurs"].get(electeur)
    if e is None:
        raise ConsultationInvalide("Copropriétaire inconnu")
    if e["choix"]:
        raise ConsultationInvalide("Ce copropriétaire a déjà voté")
    e.update(choix=choix, mode=mode, piece=(piece or "").strip()[:200] or None,
             le=(maintenant or datetime.now()).replace(microsecond=0).isoformat())
    return c


def resultat(c: dict, maintenant: datetime | None = None) -> dict:
    """Où en est la décision : adoptée seulement si TOUS ont voté pour."""
    ev = c["electeurs"].values()
    nb = len(c["electeurs"])
    pour = sum(1 for e in ev if e["choix"] == "pour")
    refus = [x for x, e in c["electeurs"].items() if e["choix"] in ("contre", "abstention")]
    attente = [x for x, e in c["electeurs"].items() if not e["choix"]]
    ecrit = any(e["mode"] in ECRIT for e in ev)
    termine = not ouverte(c, maintenant)
    if refus:
        statut, texte = "rejetee", "Décision non prise : l'unanimité n'est plus possible."
    elif not attente and (termine or not ecrit):
        statut, texte = "adoptee", "Décision prise à l'unanimité des copropriétaires."
    elif not attente:
        statut = "unanimite_acquise"
        texte = (f"Tous les copropriétaires ont voté pour. La décision sera formalisée le "
                 f"{date.fromisoformat(c['repondre_avant']).strftime('%d/%m/%Y')}, au terme du délai de réponse "
                 "(loi du 10 juillet 1965, art. 41-12).")
    elif ouverte(c, maintenant):
        statut, texte = "en_cours", f"En attente de {len(attente)} réponse{'s' if len(attente) > 1 else ''}."
    else:
        statut, texte = "caduque", "Décision non prise : tous les copropriétaires n'ont pas répondu dans le délai."
    return {"statut": statut, "texte": texte, "pour": pour, "refus": refus, "attente": attente, "nb": nb,
            "suite": None if statut in ("adoptee", "en_cours", "unanimite_acquise") else
            "La question peut être inscrite à l'ordre du jour de la prochaine assemblée générale, où elle sera "
            "votée à la majorité habituelle."}


def clore(racine: Path, copro: str, cid: str, maintenant: datetime | None = None) -> dict:
    """Clôture : à l'échéance, ou plus tôt si l'unanimité est devenue impossible, ou si tous ont voté
    en réunion (sans consultation écrite)."""
    c = charger(racine, copro, cid)
    r = resultat(c, maintenant)
    if r["statut"] == "en_cours":
        raise ConsultationInvalide("Des copropriétaires n'ont pas encore répondu et le délai court encore")
    if r["statut"] == "unanimite_acquise":
        raise ConsultationInvalide("La décision ne peut être formalisée qu'au terme du délai de réponse "
                                   "(loi du 10 juillet 1965, art. 41-12)")
    c["close_le"] = (maintenant or datetime.now()).replace(microsecond=0).isoformat()
    c["resultat"] = r["statut"]
    sauver(racine, copro, c)
    return c


def a_organiser(c: dict) -> str | None:
    """Consultation demandée par un copropriétaire : date limite pour l'organiser (art. 42-4)."""
    if not c.get("demande"):
        return None
    return (date.fromisoformat(c["demande"]["le"]) + timedelta(days=DELAI_ORGANISATION_JOURS)).isoformat()


# --------------------------------------------------------------------------- #
# Documents : bulletin papier, procès-verbal
# --------------------------------------------------------------------------- #
def _fr(iso: str) -> str:
    return date.fromisoformat(iso[:10]).strftime("%d/%m/%Y")


def bulletin_pdf(fiche: dict, c: dict, electeur: str, chemin: Path, grand: bool | None = None) -> Path:
    """Bulletin de vote papier, à renvoyer signé au syndic."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    from ag import _case
    from avis_appel import CanevasNumerote, styles, tampon
    cp = next(x for x in fiche["coproprietaires"] if x["id"] == electeur)
    grand = cp.get("grands_caracteres", False) if grand is None else grand
    S = styles(grand, papier=True)
    nom = fiche["copropriete"]["nom"]
    syndic = next((x["nom"] for x in fiche["coproprietaires"]
                   if x["id"] == fiche["gouvernance"]["syndic"]["coproprietaire_id"]), "le syndic")
    lots = ", ".join(str(l["numero"]) for l in fiche["lots"] if l["proprietaire"] == electeur)
    doc = SimpleDocTemplate(str(chemin), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=20 * mm,
                            bottomMargin=20 * mm, title=f"Bulletin de consultation – {nom}")
    cases = Table([[_case(), Paragraph(f"<b>{v}</b>", S["txt"])] for v in CHOIX.values()],
                  colWidths=[10 * mm, 164 * mm])
    cases.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 6)]))
    h = [Paragraph("Consultation des copropriétaires", S["titre"]),
         Paragraph(f"{nom} · réponse attendue au plus tard le {_fr(c['repondre_avant'])}", S["sous"]),
         Spacer(1, 5 * mm),
         Paragraph(f"{cp['nom']} · lot{'s' if ',' in lots else ''} n° {lots}", S["txt"]), Spacer(1, 4 * mm),
         Paragraph(f"<b>Question : {c['titre']}</b>", S["txt"]), Spacer(1, 2 * mm),
         Paragraph("Décision proposée :", S["txt"]),
         Paragraph(c["resolution"].replace("\n", "<br/>"), S["txt"]), Spacer(1, 5 * mm),
         Paragraph("Cochez une seule case :", S["txt"]), Spacer(1, 2 * mm), cases, Spacer(1, 6 * mm),
         Paragraph("La décision n'est prise que si tous les copropriétaires votent pour. Une abstention ou une "
                   "absence de réponse empêche la décision, qui pourra alors être soumise à une assemblée générale.",
                   S["petit"]), Spacer(1, 6 * mm),
         Paragraph(f"À renvoyer daté et signé à {syndic}, syndic.", S["txt"]), Spacer(1, 4 * mm),
         Paragraph("Fait à ............................................, le ...... / ...... / ............", S["txt"]),
         Spacer(1, 4 * mm), Paragraph("Signature :", S["txt"]), Spacer(1, 18 * mm),
         Paragraph(AVERTISSEMENT, S["petit"])]
    pied = f"{nom} – consultation {c['id']}"
    doc.build(h, canvasmaker=CanevasNumerote, onFirstPage=tampon(False, pied), onLaterPages=tampon(False, pied))
    return chemin


def proces_verbal_pdf(fiche: dict, c: dict, chemin: Path, maintenant: datetime | None = None) -> Path:
    """Procès-verbal de la consultation (décret 1967, art. 42-5), à signer par le syndic."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    from avis_appel import CanevasNumerote, S, tableau, tampon
    nom = fiche["copropriete"]["nom"]
    noms = {x["id"]: x["nom"] for x in fiche["coproprietaires"]}
    syndic = noms.get(fiche["gouvernance"]["syndic"]["coproprietaire_id"], "le syndic")
    r = resultat(c, maintenant)
    doc = SimpleDocTemplate(str(chemin), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=20 * mm,
                            bottomMargin=20 * mm, title=f"Procès-verbal de consultation – {nom}")
    from reportlab.lib.styles import ParagraphStyle
    cel = ParagraphStyle("cel_pv", parent=S["txt"], fontSize=9.5, leading=12)
    lignes = [["Copropriétaire", "Vote", "Exprimé", "Le", "Signature si présent"]]
    presents = False
    for e, v in sorted(c["electeurs"].items(), key=lambda x: noms.get(x[0], x[0])):
        present = v["mode"] in ("presence", "delegation")
        presents = presents or present
        lignes.append([Paragraph(noms.get(e, e), cel), CHOIX.get(v["choix"], "pas de réponse"),
                       Paragraph(MODES.get(v["mode"], "—") if v["mode"] else "—", cel),
                       _fr(v["le"]) if v["le"] else "—", "" if present else "—"])
    h = [Paragraph("Procès-verbal de consultation", S["titre"]),
         Paragraph(f"{nom} · consultation {c['id']} · ouverte le {_fr(c['ouverte_le'])}, réponses jusqu'au "
                   f"{_fr(c['repondre_avant'])}", S["sous"]), Spacer(1, 5 * mm),
         Paragraph("Décision soumise à la consultation des copropriétaires, en application de l'article 41-12 de la "
                   "loi du 10 juillet 1965 (petites copropriétés)"
                   + (f", à la demande de {noms.get(c['demande']['par'], c['demande']['par'])} reçue le "
                      f"{_fr(c['demande']['le'])}" if c.get("demande") else "") + ".", S["txt"]), Spacer(1, 3 * mm),
         Paragraph(f"<b>Question : {c['titre']}</b>", S["txt"]),
         Paragraph(c["resolution"].replace("\n", "<br/>"), S["txt"]), Spacer(1, 5 * mm),
         tableau(lignes, [42 * mm, 20 * mm, 58 * mm, 22 * mm, 32 * mm], aligner_droite_depuis=5, lignes_total=0,
                 serre=True), Spacer(1, 5 * mm),
         Paragraph(f"<b>Résultat : {r['texte']}</b>", S["txt"])]
    if r["suite"]:
        h.append(Paragraph(r["suite"], S["txt"]))
    h += [Spacer(1, 4 * mm),
          Paragraph("Les écrits par lesquels les copropriétaires ont exprimé ou confirmé leur vote sont annexés au "
                    "présent procès-verbal, qui est versé au registre des procès-verbaux des assemblées générales "
                    "(décret du 17 mars 1967, art. 42-5)."
                    + (" Un copropriétaire qui a participé par visioconférence ou audioconférence confirme son vote "
                       "par tout moyen dans les 48 heures ; à défaut, la décision n'est pas valablement prise."
                       if any(v["mode"] == "visio" for v in c["electeurs"].values()) else ""), S["petit"]),
          Spacer(1, 10 * mm), Paragraph(f"Établi et signé par {syndic}, syndic, le ...... / ...... / ............",
                                        S["txt"]),
          Spacer(1, 3 * mm), Paragraph("Signature :", S["txt"]), Spacer(1, 16 * mm),
          Paragraph(AVERTISSEMENT, S["petit"])]
    pied = f"{nom} – procès-verbal de consultation {c['id']}"
    doc.build(h, canvasmaker=CanevasNumerote, onFirstPage=tampon(False, pied), onLaterPages=tampon(False, pied))
    return chemin

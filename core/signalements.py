"""
signalements.py — Les copropriétaires signalent une panne, une fuite ou une dégradation ; le syndic suit.

Principes :
    - un lien secret par copropriété (et un QR code sur l'affiche du hall), sans compte à créer ;
    - des faits, jamais de noms : le formulaire le rappelle, et la liste visible de tous ne montre que
      la catégorie, le lieu, la date et l'état ; la description et la photo restent réservées au syndic ;
    - les urgences passent par le téléphone : la page affiche les numéros avant le formulaire ;
    - les photos sont réencodées (les métadonnées, dont la position GPS, disparaissent) ;
    - pour un dégât des eaux ou un acte de vandalisme, le syndic voit le délai de déclaration à l'assureur
      (au moins 5 jours ouvrés, Code des assurances, art. L113-2 ; le contrat peut prévoir plus).

Stockage : <data>/<copro>/signalements/signalements.json, photos dans le même dossier.
"""

from __future__ import annotations

import io
import json
import secrets
from datetime import date, datetime, timedelta
from pathlib import Path

CATEGORIES = {
    "fuite": {"libelle": "Fuite ou dégât des eaux", "assurance": True},
    "electricite": {"libelle": "Éclairage ou électricité des parties communes", "assurance": False},
    "acces": {"libelle": "Porte, serrure, interphone, badge", "assurance": False},
    "ascenseur": {"libelle": "Ascenseur", "assurance": False},
    "proprete": {"libelle": "Propreté, encombrants, poubelles", "assurance": False},
    "degradation": {"libelle": "Dégradation ou vandalisme", "assurance": True},
    "nuisibles": {"libelle": "Nuisibles (insectes, rongeurs)", "assurance": False},
    "autre": {"libelle": "Autre", "assurance": False},
}
NIVEAUX = {"genant": "Gênant", "urgent": "Urgent"}
STATUTS = {"recu": "Reçu", "en_cours": "En cours", "regle": "Réglé", "ecarte": "Sans suite"}
OUVERTS = ("recu", "en_cours")

DELAI_ASSURANCE_JOURS_OUVRES = 5        # minimum légal (art. L113-2 du Code des assurances), hors vol
TAILLE_MAX_PHOTO = 8 * 1024 * 1024
COTE_MAX_PHOTO = 1600
LONGUEUR_MAX = {"lieu": 120, "description": 2000, "contact": 120}

URGENCES = [
    ("Pompiers, urgence vitale", "112 ou 18"),
    ("Odeur ou fuite de gaz (GRDF, gratuit, 24 h/24)", "0 800 47 33 33"),
]


class SignalementInvalide(ValueError):
    pass


# --------------------------------------------------------------------------- #
# Stockage
# --------------------------------------------------------------------------- #
def dossier(racine: Path, copro: str) -> Path:
    return Path(racine) / copro / "signalements"


def _fichier(racine: Path, copro: str) -> Path:
    return dossier(racine, copro) / "signalements.json"


def charger(racine: Path, copro: str) -> dict:
    f = _fichier(racine, copro)
    if f.is_file():
        return json.loads(f.read_text(encoding="utf-8"))
    return {"jeton": None, "signalements": []}


def sauver(racine: Path, copro: str, donnees: dict) -> None:
    f = _fichier(racine, copro)
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(donnees, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(f)


def jeton(racine: Path, copro: str, renouveler: bool = False) -> str:
    """Le jeton du lien secret de la copropriété (créé au premier appel, renouvelable)."""
    d = charger(racine, copro)
    if renouveler or not d.get("jeton"):
        d["jeton"] = secrets.token_urlsafe(16)
        sauver(racine, copro, d)
    return d["jeton"]


def jeton_valide(racine: Path, copro: str, propose: str) -> bool:
    attendu = charger(racine, copro).get("jeton")
    return bool(attendu) and secrets.compare_digest(attendu, propose or "")


# --------------------------------------------------------------------------- #
# Photo
# --------------------------------------------------------------------------- #
def nettoyer_photo(contenu: bytes) -> bytes:
    """Vérifie que c'est une image, la réduit et la réencode en JPEG : les métadonnées (GPS, appareil) disparaissent."""
    if len(contenu) > TAILLE_MAX_PHOTO:
        raise SignalementInvalide("La photo dépasse 8 Mo.")
    from PIL import Image, ImageOps, UnidentifiedImageError
    try:
        img = Image.open(io.BytesIO(contenu))
        img = ImageOps.exif_transpose(img)
    except (UnidentifiedImageError, OSError):
        raise SignalementInvalide("Le fichier joint n'est pas une photo lisible (JPEG, PNG ou WebP).") from None
    img = img.convert("RGB")
    img.thumbnail((COTE_MAX_PHOTO, COTE_MAX_PHOTO))
    sortie = io.BytesIO()
    img.save(sortie, "JPEG", quality=82, optimize=True)
    return sortie.getvalue()


# --------------------------------------------------------------------------- #
# Signalements
# --------------------------------------------------------------------------- #
def _texte(valeur: str | None, champ: str, obligatoire: bool = False) -> str:
    t = " ".join((valeur or "").split()) if champ != "description" else (valeur or "").strip()
    if obligatoire and not t:
        raise SignalementInvalide({"lieu": "Indiquez où se trouve le problème.",
                                   "description": "Décrivez ce que vous avez constaté."}[champ])
    if len(t) > LONGUEUR_MAX[champ]:
        raise SignalementInvalide(f"Le champ « {champ} » est trop long ({LONGUEUR_MAX[champ]} caractères au plus).")
    return t


def creer(racine: Path, copro: str, categorie: str, lieu: str, description: str, niveau: str = "genant",
          contact: str = "", photo: bytes | None = None, maintenant: datetime | None = None) -> dict:
    if categorie not in CATEGORIES:
        raise SignalementInvalide("Choisissez une catégorie.")
    if niveau not in NIVEAUX:
        raise SignalementInvalide("Choisissez « gênant » ou « urgent ».")
    maintenant = maintenant or datetime.now()
    s = {
        "id": f"S{maintenant:%Y%m%d%H%M%S}{secrets.token_hex(2)}",
        "cree_le": maintenant.isoformat(timespec="minutes"),
        "categorie": categorie, "niveau": niveau,
        "lieu": _texte(lieu, "lieu", True),
        "description": _texte(description, "description", True),
        "contact": _texte(contact, "contact"),
        "statut": "recu", "note_publique": "", "maj_le": maintenant.isoformat(timespec="minutes"),
        "photo": None, "historique": [],
    }
    if photo:
        propre = nettoyer_photo(photo)
        nom = f"{s['id']}.jpg"
        d = dossier(racine, copro)
        d.mkdir(parents=True, exist_ok=True)
        (d / nom).write_bytes(propre)
        s["photo"] = nom
    donnees = charger(racine, copro)
    donnees["signalements"].insert(0, s)
    sauver(racine, copro, donnees)
    return s


def mettre_a_jour(racine: Path, copro: str, sid: str, statut: str, note_publique: str = "",
                  maintenant: datetime | None = None) -> dict:
    if statut not in STATUTS:
        raise SignalementInvalide("État inconnu.")
    if len(note_publique or "") > 300:
        raise SignalementInvalide("La note visible de tous est limitée à 300 caractères.")
    donnees = charger(racine, copro)
    s = next((x for x in donnees["signalements"] if x["id"] == sid), None)
    if s is None:
        raise KeyError(sid)
    maintenant = maintenant or datetime.now()
    if s["statut"] != statut:
        s["historique"].append({"le": maintenant.isoformat(timespec="minutes"), "de": s["statut"], "vers": statut})
    s["statut"] = statut
    s["note_publique"] = " ".join((note_publique or "").split())
    s["maj_le"] = maintenant.isoformat(timespec="minutes")
    sauver(racine, copro, donnees)
    return s


def chemin_photo(racine: Path, copro: str, sid: str) -> Path | None:
    s = next((x for x in charger(racine, copro)["signalements"] if x["id"] == sid), None)
    if not s or not s.get("photo"):
        return None
    p = dossier(racine, copro) / s["photo"]
    return p if p.is_file() else None


def vue_publique(donnees: dict, jusqu_a: int = 30) -> list[dict]:
    """Ce que voient les copropriétaires : ni description, ni photo, ni contact."""
    visibles = []
    for s in donnees["signalements"]:
        if s["statut"] == "ecarte":
            continue
        visibles.append({"categorie": CATEGORIES[s["categorie"]]["libelle"], "lieu": s["lieu"],
                         "cree_le": s["cree_le"], "statut": s["statut"], "statut_libelle": STATUTS[s["statut"]],
                         "note": s.get("note_publique", "")})
        if len(visibles) >= jusqu_a:
            break
    return visibles


def deja_signales(donnees: dict, categorie: str) -> list[dict]:
    """Signalements encore ouverts de la même catégorie, pour éviter les doublons."""
    return [s for s in donnees["signalements"] if s["categorie"] == categorie and s["statut"] in OUVERTS]


# --------------------------------------------------------------------------- #
# Assurance
# --------------------------------------------------------------------------- #
def ajouter_jours_ouvres(depart: date, n: int) -> date:
    """Jours ouvrés : du lundi au vendredi (les jours fériés ne sont pas retirés : marge à garder)."""
    d = depart
    while n > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


def delai_assurance(fiche: dict) -> int:
    for c in fiche.get("contrats", []):
        if "assurance" in c.get("objet", "").lower() and c.get("delai_declaration_jours_ouvres"):
            return max(int(c["delai_declaration_jours_ouvres"]), DELAI_ASSURANCE_JOURS_OUVRES)
    return DELAI_ASSURANCE_JOURS_OUVRES


def limite_declaration(fiche: dict, s: dict) -> date | None:
    if not CATEGORIES[s["categorie"]]["assurance"]:
        return None
    return ajouter_jours_ouvres(datetime.fromisoformat(s["cree_le"]).date(), delai_assurance(fiche))


def astreintes(fiche: dict) -> list[tuple[str, str]]:
    """Numéros d'astreinte déclarés dans les contrats de la fiche (« telephone_astreinte »)."""
    return [(f"{c['objet']} ({c['prestataire']})", c["telephone_astreinte"])
            for c in fiche.get("contrats", []) if c.get("telephone_astreinte")]


# --------------------------------------------------------------------------- #
# Tableau de bord du syndic
# --------------------------------------------------------------------------- #
def taches(racine: Path, copro: str, fiche: dict, jour: date) -> list[dict]:
    donnees = charger(racine, copro)
    ouverts = [s for s in donnees["signalements"] if s["statut"] in OUVERTS]
    t = []
    nouveaux = [s for s in ouverts if s["statut"] == "recu"]
    urgents = [s for s in nouveaux if s["niveau"] == "urgent"]
    if urgents:
        t.append({"texte": f"{len(urgents)} signalement{'s' if len(urgents) > 1 else ''} urgent{'s' if len(urgents) > 1 else ''}",
                  "detail": ", ".join(f"{CATEGORIES[s['categorie']]['libelle'].lower()} ({s['lieu']})" for s in urgents[:3]),
                  "lien": f"/app/{copro}/signalements", "niveau": "urgent"})
    autres = len(nouveaux) - len(urgents)
    if autres:
        t.append({"texte": f"{autres} nouveau{'x' if autres > 1 else ''} signalement{'s' if autres > 1 else ''}",
                  "detail": "À prendre en compte, puis à passer « en cours » pour que les voisins le voient.",
                  "lien": f"/app/{copro}/signalements", "niveau": "important"})
    for s in ouverts:
        limite = limite_declaration(fiche, s)
        if limite and jour <= limite and not s.get("declare_assurance"):
            t.append({"texte": f"Déclarer à l'assurance : {CATEGORIES[s['categorie']]['libelle'].lower()}",
                      "detail": f"{s['lieu']}. Délai : au plus tard le {limite.day:02d}/{limite.month:02d}/{limite.year} "
                                f"({delai_assurance(fiche)} jours ouvrés). Vérifiez le délai de votre contrat.",
                      "lien": f"/app/{copro}/signalements#{s['id']}", "niveau": "urgent"})
    return t


def marquer_declare(racine: Path, copro: str, sid: str, maintenant: datetime | None = None) -> None:
    donnees = charger(racine, copro)
    s = next(x for x in donnees["signalements"] if x["id"] == sid)
    s["declare_assurance"] = (maintenant or datetime.now()).isoformat(timespec="minutes")
    sauver(racine, copro, donnees)


# --------------------------------------------------------------------------- #
# Affiche du hall, avec QR code
# --------------------------------------------------------------------------- #
def affiche(fiche: dict, url: str, chemin: Path | None = None) -> bytes:
    """Une page A4 à afficher dans le hall : comment signaler, QR code, numéros d'urgence."""
    from reportlab.graphics import renderPDF
    from reportlab.graphics.barcode.qr import QrCodeWidget
    from reportlab.graphics.shapes import Drawing
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    from avis_appel import polices  # Atkinson Hyperlegible, comme les autres affiches du hall

    normale, grasse = polices(True)
    tampon = io.BytesIO()
    c = canvas.Canvas(tampon, pagesize=A4)
    c.setTitle("Signaler un problème dans l’immeuble")
    larg, haut = A4
    x = 22 * mm
    y = haut - 30 * mm
    c.setFillColorRGB(0.11, 0.1, 0.09)
    c.setFont(grasse, 30)
    c.drawString(x, y, "Un problème dans l’immeuble ?")
    y -= 13 * mm
    c.setFont(normale, 15)
    for ligne in ("Panne, fuite, porte qui ferme mal, dégradation :",
                  "signalez-le au syndic en scannant ce code avec votre téléphone."):
        c.drawString(x, y, ligne)
        y -= 7.5 * mm

    cote = 80 * mm
    w = QrCodeWidget(url)
    w.barLevel = "M"
    b = w.getBounds()
    d = Drawing(cote, cote, transform=[cote / (b[2] - b[0]), 0, 0, cote / (b[3] - b[1]), 0, 0])
    d.add(w)
    y -= cote + 6 * mm
    renderPDF.draw(d, c, (larg - cote) / 2, y)
    y -= 8 * mm
    c.setFont(normale, 11)
    c.drawCentredString(larg / 2, y, url)

    y -= 16 * mm
    c.setFont(grasse, 17)
    c.drawString(x, y, "En cas d’urgence, appelez d’abord :")
    y -= 9 * mm
    c.setFont(normale, 14)
    for libelle, numero in URGENCES + astreintes(fiche):
        c.setFont(grasse, 14)
        c.drawString(x, y, numero)
        c.setFont(normale, 14)
        c.drawString(x + 48 * mm, y, libelle)
        y -= 8 * mm
    y -= 6 * mm
    c.setFont(normale, 11)
    c.setFillColorRGB(0.34, 0.33, 0.31)
    for ligne in ("Sans téléphone ? Déposez un mot dans la boîte aux lettres du syndic.",
                  "Décrivez ce qui est abîmé ou en panne ; ne nommez personne.",
                  f"{fiche['copropriete']['nom']}"):
        c.drawString(x, y, ligne)
        y -= 6 * mm
    c.showPage()
    c.save()
    pdf = tampon.getvalue()
    if chemin:
        Path(chemin).write_bytes(pdf)
    return pdf

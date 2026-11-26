"""
pieces.py — Des comptes consultables : une pièce justificative pour chaque dépense.

Le soupçon (« il se sert dans la caisse ») est le premier motif de conflit dans les petites
copropriétés. La meilleure protection du syndic bénévole, c'est la transparence : chaque dépense
de l'exercice, avec la facture ou le justificatif qui la fonde, consultable toute l'année par les
copropriétaires. La loi n'impose cette consultation qu'avant l'assemblée qui approuve les comptes
(loi du 10 juillet 1965, art. 18-1) : Mitoyen permet d'aller plus loin, si le syndic le décide.

    - une pièce par charge : la facture saisie, ou la dépense directe du relevé (frais bancaires,
      petit achat) ;
    - PDF, JPEG ou PNG, 8 Mo au plus. Les photos sont réenregistrées sans leurs métadonnées
      (position GPS, appareil) ; les PDF, sans leurs propriétés (auteur, logiciel) ;
    - une pièce peut être marquée « privée » quand elle contient une donnée personnelle (une
      facture d'avocat qui nomme un copropriétaire débiteur, par exemple) : elle n'est alors
      montrée que sur demande au syndic ;
    - le lien de consultation est désactivé par défaut, renouvelable à tout moment, jamais
      indexé par les moteurs de recherche.

La page publique ne montre aucun nom de copropriétaire : seulement les fournisseurs, les montants
et les comptes de charge. Pour une dépense directe, c'est le fournisseur saisi qui s'affiche, pas le
libellé brut du relevé bancaire (qui peut contenir un nom).
"""

from __future__ import annotations

import io
import json
import re
import secrets
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

TAILLE_MAX = 8 * 1024 * 1024
COTE_MAX_IMAGE = 2400
CLE = re.compile(r"^(facture|depense):[A-Za-z0-9_-]{1,64}$")
ZERO = Decimal("0")


class PieceInvalide(ValueError):
    pass


# --------------------------------------------------------------------------- #
# Stockage
# --------------------------------------------------------------------------- #
def _dossier(racine: Path, copro: str) -> Path:
    return Path(racine) / copro / "compta" / "pieces"


def _index(racine: Path, copro: str) -> Path:
    return Path(racine) / copro / "compta" / "pieces.json"


def charger(racine: Path, copro: str) -> dict:
    f = _index(racine, copro)
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}


def _ecrire(racine: Path, copro: str, idx: dict) -> None:
    f = _index(racine, copro)
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(f)


def nature(contenu: bytes) -> str:
    if contenu[:5] == b"%PDF-":
        return "pdf"
    if contenu[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if contenu[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    raise PieceInvalide("Format accepté : PDF, JPEG ou PNG")


def nettoyer(contenu: bytes, kind: str) -> tuple[bytes, str]:
    """Retire les métadonnées. Les images deviennent un JPEG sans EXIF, réduit si très grand."""
    if kind == "pdf":
        try:
            from pypdf import PdfReader, PdfWriter
            r = PdfReader(io.BytesIO(contenu))
            if r.is_encrypted:
                raise PieceInvalide("PDF protégé par un mot de passe : enregistrez-le sans protection")
            w = PdfWriter()
            for p in r.pages:
                w.add_page(p)
            sortie = io.BytesIO()
            w.write(sortie)
            return sortie.getvalue(), "pdf"
        except PieceInvalide:
            raise
        except Exception:
            raise PieceInvalide("Ce PDF n'a pas pu être lu")
    from PIL import Image, ImageOps
    try:
        im = Image.open(io.BytesIO(contenu))
        im = ImageOps.exif_transpose(im)               # garder le bon sens avant de jeter l'EXIF
        im.thumbnail((COTE_MAX_IMAGE, COTE_MAX_IMAGE))
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        sortie = io.BytesIO()
        im.save(sortie, "JPEG", quality=85, optimize=True)   # aucune métadonnée recopiée
        return sortie.getvalue(), "jpeg"
    except Exception:
        raise PieceInvalide("Cette image n'a pas pu être lue")


def ajouter(racine: Path, copro: str, cle: str, contenu: bytes, nom: str, jour: date,
            privee: bool = False) -> dict:
    """Joint (ou remplace) la pièce d'une facture (« facture:F0003 ») ou d'une dépense directe
    (« depense:<opération du relevé> »)."""
    if not CLE.match(cle):
        raise PieceInvalide("Dépense inconnue")
    if not contenu:
        raise PieceInvalide("Fichier vide")
    if len(contenu) > TAILLE_MAX:
        raise PieceInvalide("Fichier trop lourd : 8 Mo au plus")
    propre, kind = nettoyer(contenu, nature(contenu))
    d = _dossier(racine, copro)
    d.mkdir(parents=True, exist_ok=True)
    idx = charger(racine, copro)
    ancien = idx.get(cle)
    fichier = f"{cle.replace(':', '_')}_{secrets.token_hex(4)}.{'pdf' if kind == 'pdf' else 'jpg'}"
    (d / fichier).write_bytes(propre)
    if ancien and (d / ancien["fichier"]).is_file():
        (d / ancien["fichier"]).unlink()
    nom_propre = re.sub(r"[^\w .()-]+", "", Path(nom or "piece").name)[:80] or "piece"
    idx[cle] = {"fichier": fichier, "type": kind, "nom": nom_propre, "ajoutee_le": jour.isoformat(),
                "octets": len(propre), "privee": bool(privee)}
    _ecrire(racine, copro, idx)
    return idx[cle]


def retirer(racine: Path, copro: str, cle: str) -> None:
    idx = charger(racine, copro)
    p = idx.pop(cle, None)
    if p is None:
        raise PieceInvalide("Aucune pièce pour cette dépense")
    f = _dossier(racine, copro) / p["fichier"]
    if f.is_file():
        f.unlink()
    _ecrire(racine, copro, idx)


def rendre_privee(racine: Path, copro: str, cle: str, privee: bool) -> dict:
    idx = charger(racine, copro)
    if cle not in idx:
        raise PieceInvalide("Aucune pièce pour cette dépense")
    idx[cle]["privee"] = bool(privee)
    _ecrire(racine, copro, idx)
    return idx[cle]


def fichier(racine: Path, copro: str, cle: str) -> tuple[Path, str] | None:
    p = charger(racine, copro).get(cle)
    if not p:
        return None
    f = _dossier(racine, copro) / p["fichier"]
    return (f, "application/pdf" if p["type"] == "pdf" else "image/jpeg") if f.is_file() else None


# --------------------------------------------------------------------------- #
# Les charges de l'exercice, avec leurs pièces
# --------------------------------------------------------------------------- #
def charges(E: list[dict], st: dict, idx: dict, du: str, au: str) -> dict:
    """Chaque écriture de charge (classe 6) de la période, avec sa pièce.
    st : compta.charger() (factures, dépenses) ; idx : charger()."""
    from compta import libelle_compte
    factures = {f["id"]: f for f in st.get("factures", [])}
    dep = st.get("depenses", {})
    lignes = []
    for e in E:
        if not du <= e["date"] <= au:
            continue
        for l in e["lignes"]:
            if not str(l["compte"]).startswith("6"):
                continue
            montant = Decimal(str(l["debit"])) - Decimal(str(l["credit"]))
            if not montant:
                continue
            if e["source"] == "facture" and e["piece"] in factures:
                f = factures[e["piece"]]
                cle, fournisseur, objet = f"facture:{f['id']}", f["fournisseur"], f.get("libelle") or ""
            elif e["source"] == "banque" and e["piece"] in dep:
                a = dep[e["piece"]]
                cle, fournisseur, objet = f"depense:{e['piece']}", a.get("fournisseur") or "", ""
            else:
                cle, fournisseur, objet = None, "", ""
            compte = str(l["compte"])
            if objet.strip().lower() == libelle_compte(compte).strip().lower():
                objet = ""                                  # libellé par défaut : rien à ajouter
            p = idx.get(cle) if cle else None
            lignes.append({"date": e["date"], "cle": cle, "fournisseur": fournisseur or "Dépense directe",
                           "objet": objet, "compte": compte, "libelle_compte": libelle_compte(compte),
                           "montant": montant,
                           "piece": None if not p else {"type": p["type"], "privee": p["privee"], "nom": p["nom"]}})
    lignes.sort(key=lambda x: (x["date"], x["fournisseur"]))
    par_compte: dict[str, dict] = {}
    for x in lignes:
        c = par_compte.setdefault(x["compte"], {"compte": x["compte"], "libelle": x["libelle_compte"], "total": ZERO})
        c["total"] += x["montant"]
    total = sum((x["montant"] for x in lignes), ZERO)
    justifiees = sum(1 for x in lignes if x["piece"])
    return {"du": du, "au": au, "lignes": lignes, "par_compte": sorted(par_compte.values(), key=lambda c: c["compte"]),
            "total": total, "nb": len(lignes), "justifiees": justifiees,
            "montant_justifie": sum((x["montant"] for x in lignes if x["piece"]), ZERO)}


# --------------------------------------------------------------------------- #
# Lien de consultation (désactivé par défaut)
# --------------------------------------------------------------------------- #
def _reglages(racine: Path, copro: str) -> Path:
    return Path(racine) / copro / "comptes_consultables.json"


def reglages(racine: Path, copro: str) -> dict:
    f = _reglages(racine, copro)
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {"jeton": None, "actif": False}


def partager(racine: Path, copro: str, actif: bool, renouveler: bool = False) -> dict:
    r = reglages(racine, copro)
    if actif and (renouveler or not r.get("jeton")):
        r["jeton"] = secrets.token_urlsafe(16)
    r["actif"] = bool(actif)
    r["modifie_le"] = datetime.now().replace(microsecond=0).isoformat()
    f = _reglages(racine, copro)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(r), encoding="utf-8")
    return r


def jeton_valide(racine: Path, copro: str, propose: str) -> bool:
    r = reglages(racine, copro)
    return bool(r.get("actif") and r.get("jeton")) and secrets.compare_digest(r["jeton"], propose or "")

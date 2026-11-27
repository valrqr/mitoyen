"""
absence.py — « Je pars en vacances » : le syndic s'absente sans que la copropriété reste sans réponse.

Le syndic ne se fait pas remplacer : seul responsable de sa gestion, il ne peut se faire substituer,
et seule l'assemblée générale peut autoriser une délégation de pouvoir à une fin déterminée (loi du
10 juillet 1965, art. 18, majorité de l'article 25 ; à vérifier sur Légifrance). Mitoyen l'aide donc à :

1. préparer avant de partir ce qui tombe pendant l'absence (appels de fonds, convocation d'AG,
   contrats, diagnostics…), pour que rien n'attende son retour ;
2. prévenir les copropriétaires : la page de signalement affiche la date de retour et, si le relais
   l'accepte, son numéro pour les urgences ;
3. donner au relais (un voisin de confiance) une page privée, valable pendant l'absence seulement :
   les signalements en cours et les numéros d'astreinte. Le relais ne voit ni les comptes ni les noms
   de ceux qui signalent. Il ne décide rien à la place du syndic, sauf si l'AG lui a délégué les
   urgences : Mitoyen fournit le projet de résolution.

Stockage : data/<copro>/absence.json.
"""

from __future__ import annotations

import json
import re
import secrets
from datetime import date, timedelta
from pathlib import Path

DUREE_MAX_JOURS = 92                  # au-delà, ce n'est plus une absence : voir le plan de relève
MARGE_RETOUR_JOURS = 7                # ce qui tombe la semaine du retour se prépare aussi avant
LONGUEUR_MAX = {"nom": 80, "telephone": 20, "email": 120, "message": 300}
TELEPHONE = re.compile(r"^\+?[0-9 .]{8,20}$")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AbsenceInvalide(ValueError):
    pass


# --------------------------------------------------------------------------- #
# Stockage
# --------------------------------------------------------------------------- #
def _fichier(racine: Path, copro: str) -> Path:
    return Path(racine) / copro / "absence.json"


def charger(racine: Path, copro: str) -> dict | None:
    f = _fichier(racine, copro)
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else None


def _sauver(racine: Path, copro: str, a: dict) -> dict:
    f = _fichier(racine, copro)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")
    return a


def annuler(racine: Path, copro: str) -> None:
    f = _fichier(racine, copro)
    if f.is_file():
        f.unlink()


def _texte(saisie: dict, champ: str) -> str:
    v = " ".join(str(saisie.get(champ) or "").split())
    if len(v) > LONGUEUR_MAX[champ]:
        raise AbsenceInvalide(f"{champ.capitalize()} trop long ({LONGUEUR_MAX[champ]} caractères au plus)")
    return v


def enregistrer(racine: Path, copro: str, saisie: dict, jour: date) -> dict:
    """saisie : du, au (AAAA-MM-JJ), relais_nom, relais_telephone, relais_email, telephone_public ("1"),
    message. Le relais est facultatif ; son numéro n'est montré aux voisins que s'il l'a accepté."""
    try:
        du, au = date.fromisoformat(str(saisie.get("du"))), date.fromisoformat(str(saisie.get("au")))
    except ValueError:
        raise AbsenceInvalide("Indiquez les dates de départ et de retour")
    if au < du:
        raise AbsenceInvalide("La date de retour précède la date de départ")
    if au < jour:
        raise AbsenceInvalide("Cette absence est déjà terminée")
    if (au - du).days > DUREE_MAX_JOURS:
        raise AbsenceInvalide("Plus de trois mois : ce n'est plus une absence. Désignez un nouveau syndic ou "
                              "préparez le plan de relève")
    nom =_texte({"nom": saisie.get("relais_nom")}, "nom")
    tel = _texte({"telephone": saisie.get("relais_telephone")}, "telephone")
    email = _texte({"email": saisie.get("relais_email")}, "email")
    if tel and not TELEPHONE.match(tel):
        raise AbsenceInvalide("Numéro du relais illisible")
    if email and not EMAIL.match(email):
        raise AbsenceInvalide("Adresse électronique du relais illisible")
    if (tel or email) and not nom:
        raise AbsenceInvalide("Indiquez le nom du relais")
    public = str(saisie.get("telephone_public") or "") == "1"
    if public and not tel:
        raise AbsenceInvalide("Pour l'afficher aux voisins, indiquez le numéro du relais")
    ancien = charger(racine, copro) or {}
    a = {"du": du.isoformat(), "au": au.isoformat(),
         "relais": {"nom": nom, "telephone": tel, "email": email} if nom else None,
         "telephone_public": public, "message": _texte(saisie, "message"),
         "jeton_relais": ancien.get("jeton_relais") or secrets.token_urlsafe(16)}
    return _sauver(racine, copro, a)


# --------------------------------------------------------------------------- #
# État
# --------------------------------------------------------------------------- #
def en_cours(a: dict | None, jour: date) -> bool:
    return bool(a) and a["du"] <= jour.isoformat() <= a["au"]


def prevue(a: dict | None, jour: date) -> bool:
    return bool(a) and jour.isoformat() < a["du"]


def retour(a: dict) -> date:
    return date.fromisoformat(a["au"]) + timedelta(days=1)


def jeton_relais_valide(a: dict | None, propose: str, jour: date) -> bool:
    """La page du relais ne s'ouvre que pendant l'absence (et la veille du départ, pour la découvrir)."""
    if not a or not a.get("relais") or not a.get("jeton_relais"):
        return False
    debut = date.fromisoformat(a["du"]) - timedelta(days=1)
    return debut <= jour <= date.fromisoformat(a["au"]) and secrets.compare_digest(a["jeton_relais"], propose or "")


def _date_fr(d: date) -> str:
    return f"{d.day}{'er' if d.day == 1 else ''} " + \
        ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
         "novembre", "décembre"][d.month - 1]


def avis_voisins(a: dict | None, jour: date) -> dict | None:
    """Ce que voient les copropriétaires sur la page de signalement pendant l'absence."""
    if not en_cours(a, jour):
        return None
    texte = (f"Le syndic est absent jusqu'au {_date_fr(date.fromisoformat(a['au']))} inclus. "
             "Votre signalement est bien enregistré et sera traité à son retour.")
    if a.get("message"):
        texte += " " + a["message"]
    contact = None
    if a.get("relais") and a.get("telephone_public") and a["relais"].get("telephone"):
        contact = {"libelle": f"Urgence pour l'immeuble pendant l'absence : {a['relais']['nom']}",
                   "telephone": a["relais"]["telephone"]}
    return {"texte": texte, "contact": contact}


# --------------------------------------------------------------------------- #
# Ce qui tombe pendant l'absence
# --------------------------------------------------------------------------- #
def a_preparer(a: dict, jour: date, appels: list[dict], envoi_jours_avant: int,
               ag: dict | None, alertes: list[dict]) -> list[dict]:
    """Les tâches dont l'échéance tombe entre aujourd'hui et la semaine qui suit le retour.

    appels : [{trimestre, date (date), statut}] ; ag : {id, date, limite_notification} ou None ;
    alertes : celles de l'échéancier ({type, titre, message, date}).
    Chaque tâche : {quand (date), titre, detail, lien_type, automatique (bool)}."""
    fin = date.fromisoformat(a["au"]) + timedelta(days=MARGE_RETOUR_JOURS)
    t = []
    for x in appels:
        envoi = x["date"] - timedelta(days=envoi_jours_avant)
        if jour <= x["date"] and envoi <= fin and x.get("statut") != "valide":
            t.append({"quand": min(max(envoi, jour), x["date"]),
                      "titre": f"Appel de fonds du {x['trimestre']}{'er' if x['trimestre'] == 1 else 'e'} trimestre",
                      "detail": f"Exigible le {x['date']:%d/%m/%Y}, avis à envoyer {envoi_jours_avant} jours avant. "
                                "Générez-le et validez-le avant de partir.",
                      "lien_type": "appels", "automatique": False})
    if ag:
        d_ag = date.fromisoformat(ag["date"])
        limite = date.fromisoformat(ag["limite_notification"])
        if jour <= limite <= fin:
            t.append({"quand": limite, "titre": "Convocations de l'AG",
                      "detail": f"À notifier au plus tard le {limite:%d/%m/%Y} pour l'AG du {d_ag:%d/%m/%Y}.",
                      "lien_type": "ag", "ag": ag["id"], "automatique": False})
        if jour <= d_ag <= fin:
            t.append({"quand": d_ag, "titre": "L'assemblée générale a lieu pendant votre absence",
                      "detail": "Le syndic doit y être : déplacez la date, ou revenez pour la séance. Les rappels "
                                "aux copropriétaires, eux, partent tout seuls.",
                      "lien_type": "ag", "ag": ag["id"], "automatique": False})
    for al in alertes:
        if al.get("type") == "impayes" or not al.get("date"):
            continue
        d = date.fromisoformat(al["date"])
        if jour <= d <= fin:
            t.append({"quand": d, "titre": al["titre"], "detail": al["message"], "lien_type": al["type"],
                      "automatique": False})
    t.sort(key=lambda x: x["quand"])
    return t


# --------------------------------------------------------------------------- #
# La délégation des urgences, à voter en AG
# --------------------------------------------------------------------------- #
def resolution_delegation(relais: str, plafond: int) -> str:
    """Projet de résolution : l'AG délègue au relais les seules mesures urgentes, plafonnées."""
    nom = relais or "[nom du copropriétaire relais]"
    montant = f"{plafond:,}".replace(",", " ") + " €" if plafond else "[montant] €"
    return (f"L'assemblée générale autorise une délégation de pouvoir à {nom}, copropriétaire, à la seule fin "
            "de faire réaliser, pendant les absences du syndic et lorsqu'il ne peut être joint, les mesures "
            "urgentes nécessaires à la sauvegarde de l'immeuble (fuite, panne d'éclairage ou de porte, mise en "
            f"sécurité), dans la limite de {montant} TTC par intervention. Le délégué informe le syndic sans délai "
            "et lui remet le devis ou la facture. Cette délégation prend fin avec le mandat du syndic en cours. "
            "(Loi du 10 juillet 1965, art. 18 ; majorité de l'article 25.)")

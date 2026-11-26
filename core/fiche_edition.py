"""
fiche_edition.py — Modifier la fiche de la copropriété depuis l'interface, sans toucher au YAML.

La fiche décrite dans config/<copro>.yaml reste la base (avec ses commentaires). Chaque
modification faite dans l'interface est ajoutée à un journal, data/<copro>/fiche_modifications.json,
rejoué à chaque lecture de la fiche. Trois avantages :

    - le YAML n'est jamais réécrit : ses commentaires et sa mise en forme restent intacts ;
    - chaque modification est datée et motivée : c'est la trace qui protège le syndic bénévole
      (« le nouveau copropriétaire a été inscrit le 12 mars, après l'avis de mutation ») ;
    - les données réelles restent dans data/, jamais versionné.

Ce qui se modifie :
    - un copropriétaire : nom, coordonnées, canal d'envoi, grands caractères, demande de papier,
      proche aidant ;
    - un nouveau copropriétaire (identifiant attribué automatiquement) ;
    - le propriétaire d'un ou plusieurs lots, après une vente.

Un ancien copropriétaire n'est jamais effacé : ses comptes (et une éventuelle dette du vendeur)
restent lisibles. Quand il n'a plus de lot, il est marqué « ancien » et ne reçoit plus les envois
de la copropriété.

Chaque modification est validée sur la fiche complète avant d'être enregistrée : une modification
qui rendrait la fiche incohérente est refusée avec un message lisible.

Jamais de coordonnées bancaires ni de code d'accès : ces champs ne sont pas modifiables ici.
"""

from __future__ import annotations

import copy
import json
import re
from datetime import date, datetime
from pathlib import Path

FICHIER = "fiche_modifications.json"
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CHAMPS_TEXTE = {"nom": 120, "email": 160, "telephone": 30, "adresse": 200}
CANAUX = ("email", "courrier")


class FicheInvalide(ValueError):
    pass


# --------------------------------------------------------------------------- #
# Journal
# --------------------------------------------------------------------------- #
def _chemin(racine: Path, copro: str) -> Path:
    return Path(racine) / copro / FICHIER


def journal(racine: Path, copro: str) -> list[dict]:
    f = _chemin(racine, copro)
    return json.loads(f.read_text(encoding="utf-8"))["journal"] if f.is_file() else []


def _ecrire(racine: Path, copro: str, j: list[dict]) -> None:
    f = _chemin(racine, copro)
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps({"journal": j}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    tmp.replace(f)


def _date(v):
    if v in (None, "") or isinstance(v, date):
        return v or None
    return date.fromisoformat(str(v)[:10])


def _appliquer_une(f: dict, m: dict) -> None:
    copros = {c["id"]: c for c in f["coproprietaires"]}
    if m["action"] == "coproprietaire_ajout":
        c = dict(m["coproprietaire"])
        for k in ("demande_papier", "aidant"):
            if c.get(k):
                c[k] = {kk: (_date(vv) if kk.endswith("_le") else vv) for kk, vv in c[k].items()}
        f["coproprietaires"].append(c)
    elif m["action"] == "coproprietaire_maj":
        c = copros[m["id"]]
        for k, v in m["champs"].items():
            if v is None:
                c.pop(k, None)
            elif k in ("demande_papier", "aidant"):
                c[k] = {kk: (_date(vv) if kk.endswith("_le") else vv) for kk, vv in v.items()}
            else:
                c[k] = v
    elif m["action"] == "lots_proprietaire":
        for l in f["lots"]:
            if l["numero"] in m["lots"]:
                l["proprietaire"] = m["nouveau"]
        for cid in {m["ancien"]} if m.get("ancien") else set():
            if cid in copros and not any(l["proprietaire"] == cid for l in f["lots"]):
                copros[cid]["ancien"] = True
                copros[cid]["ancien_depuis"] = _date(m["le"])
        if m["nouveau"] in copros:
            copros[m["nouveau"]].pop("ancien", None)
            copros[m["nouveau"]].pop("ancien_depuis", None)
    else:
        raise FicheInvalide(f"Modification inconnue : {m['action']}")


def appliquer(fiche: dict, modifications: list[dict]) -> dict:
    """La fiche à jour : la base, puis chaque modification du journal, dans l'ordre."""
    f = copy.deepcopy(fiche)
    for m in modifications:
        _appliquer_une(f, m)
    return f


def fiche_a_jour(fiche_base: dict, racine: Path, copro: str) -> dict:
    j = journal(racine, copro)
    return appliquer(fiche_base, j) if j else fiche_base


def _enregistrer(racine: Path, copro: str, fiche_base: dict, m: dict) -> dict:
    """Valide la fiche complète avec la modification, puis l'ajoute au journal."""
    from fiche_copro import valider
    j = journal(racine, copro)
    nouvelle = appliquer(fiche_base, j + [m])
    rapport = valider(nouvelle)
    if not rapport.ok:
        raise FicheInvalide("La fiche deviendrait incohérente : " + " ; ".join(rapport.erreurs))
    _ecrire(racine, copro, j + [m])
    return nouvelle


# --------------------------------------------------------------------------- #
# Contrôles des champs saisis
# --------------------------------------------------------------------------- #
def _texte(v, n: int) -> str | None:
    v = re.sub(r"\s+", " ", str(v or "")).strip()
    return v[:n] or None


def champs_coproprietaire(saisie: dict) -> dict:
    """Nettoie et contrôle les champs saisis. None = champ effacé."""
    c = {k: _texte(saisie.get(k), n) for k, n in CHAMPS_TEXTE.items() if k in saisie}
    if "nom" in c and not c["nom"]:
        raise FicheInvalide("Le nom est obligatoire")
    if c.get("email") and not EMAIL.match(c["email"]):
        raise FicheInvalide(f"Adresse électronique invalide : {c['email']}")
    if "email" in c and c["email"]:
        c["email"] = c["email"].lower()
    if "envoi" in saisie:
        if saisie["envoi"] not in CANAUX:
            raise FicheInvalide("Canal d'envoi : mail ou courrier")
        c["envoi"] = saisie["envoi"]
    if "grands_caracteres" in saisie:
        c["grands_caracteres"] = True if saisie["grands_caracteres"] in (True, "true", "on", "1") else None
    if "demande_papier_le" in saisie:
        le = _date(saisie.get("demande_papier_le"))
        if le:
            from papier import MOYENS_DEMANDE
            moyen = saisie.get("demande_papier_moyen") or "lettre_recommandee"
            if moyen not in MOYENS_DEMANDE:
                raise FicheInvalide("Moyen de la demande de courrier inconnu")
            c["demande_papier"] = {"recue_le": le.isoformat(), "moyen": moyen}
        else:
            c["demande_papier"] = None
    if "aidant_nom" in saisie:
        nom = _texte(saisie.get("aidant_nom"), 120)
        if nom:
            mail = _texte(saisie.get("aidant_email"), 160)
            if mail and not EMAIL.match(mail):
                raise FicheInvalide(f"Adresse électronique de l'aidant invalide : {mail}")
            accord = _date(saisie.get("aidant_consentement_le"))
            if not accord:
                raise FicheInvalide("Un proche aidant ne reçoit les documents qu'avec l'accord écrit du "
                                    "copropriétaire : indiquez la date de cet accord")
            c["aidant"] = {"nom": nom, **({"email": mail.lower()} if mail else {}),
                           "consentement_le": accord.isoformat()}
        else:
            c["aidant"] = None
    return c


def _nouvel_id(fiche: dict) -> str:
    ids = [c["id"] for c in fiche["coproprietaires"]]
    m = re.match(r"^([A-Za-z]+)(\d+)$", ids[0]) if ids else None
    prefixe, largeur = (m.group(1), len(m.group(2))) if m else ("CP", 2)
    nums = [int(re.sub(r"\D", "", i) or 0) for i in ids if i.startswith(prefixe)]
    return f"{prefixe}{max(nums, default=0) + 1:0{largeur}d}"


# --------------------------------------------------------------------------- #
# Les trois modifications
# --------------------------------------------------------------------------- #
def modifier_coproprietaire(racine: Path, copro: str, fiche_base: dict, cid: str, saisie: dict,
                            le: date, motif: str = "") -> dict:
    actuelle = fiche_a_jour(fiche_base, racine, copro)
    c = next((x for x in actuelle["coproprietaires"] if x["id"] == cid), None)
    if c is None:
        raise FicheInvalide(f"Copropriétaire inconnu : {cid}")
    champs = champs_coproprietaire(saisie)
    # seules les vraies modifications entrent au journal
    def norm(v):
        return v.isoformat() if isinstance(v, date) else v
    utiles = {k: v for k, v in champs.items()
              if (v is None and k in c) or (v is not None and (json.dumps(norm(c.get(k)), default=str, sort_keys=True)
                                                                != json.dumps(v, default=str, sort_keys=True)))}
    if not utiles:
        raise FicheInvalide("Aucune modification")
    m = {"le": le.isoformat(), "enregistre_le": datetime.now().replace(microsecond=0).isoformat(),
         "action": "coproprietaire_maj", "id": cid, "champs": utiles, "motif": _texte(motif, 200)}
    return _enregistrer(racine, copro, fiche_base, m)


def changer_proprietaire(racine: Path, copro: str, fiche_base: dict, numeros: list[int], le: date,
                         nouveau: str | None = None, nouveau_saisie: dict | None = None,
                         motif: str = "vente") -> tuple[str, dict]:
    """Le ou les lots passent à un autre copropriétaire (vente, succession, donation…) :
    un copropriétaire déjà inscrit (nouveau) ou une nouvelle personne (nouveau_saisie).
    L'inscription de la nouvelle personne et le transfert des lots forment une seule opération,
    validée d'un bloc : jamais de copropriétaire sans lot dans la fiche."""
    actuelle = fiche_a_jour(fiche_base, racine, copro)
    lots = [l for l in actuelle["lots"] if l["numero"] in numeros]
    if not numeros or len(lots) != len(set(numeros)):
        raise FicheInvalide("Choisissez au moins un lot existant")
    anciens = {l["proprietaire"] for l in lots}
    if len(anciens) != 1:
        raise FicheInvalide("Les lots choisis appartiennent à des copropriétaires différents : "
                            "une modification par vendeur")
    ancien = anciens.pop()
    horodatage = datetime.now().replace(microsecond=0).isoformat()
    ajout = []
    if nouveau_saisie is not None:
        champs = {k: v for k, v in champs_coproprietaire(nouveau_saisie).items() if v is not None}
        if not champs.get("nom"):
            raise FicheInvalide("Le nom du nouveau copropriétaire est obligatoire")
        champs.setdefault("envoi", "email" if champs.get("email") else "courrier")
        nouveau = _nouvel_id(actuelle)
        ajout = [{"le": le.isoformat(), "enregistre_le": horodatage, "action": "coproprietaire_ajout",
                  "coproprietaire": {"id": nouveau, **champs}, "motif": _texte(motif, 200) or "vente"}]
    elif not any(c["id"] == nouveau for c in actuelle["coproprietaires"]):
        raise FicheInvalide(f"Copropriétaire inconnu : {nouveau}")
    if nouveau == ancien:
        raise FicheInvalide("Ces lots appartiennent déjà à ce copropriétaire")
    transfert = {"le": le.isoformat(), "enregistre_le": horodatage, "action": "lots_proprietaire",
                 "lots": sorted(numeros), "ancien": ancien, "nouveau": nouveau,
                 "motif": _texte(motif, 200) or "vente"}
    from fiche_copro import valider
    j = journal(racine, copro)
    nouvelle = appliquer(fiche_base, j + ajout + [transfert])
    rapport = valider(nouvelle)
    if not rapport.ok:
        raise FicheInvalide("La fiche deviendrait incohérente : " + " ; ".join(rapport.erreurs))
    _ecrire(racine, copro, j + ajout + [transfert])
    return nouveau, nouvelle


def historique(fiche: dict, j: list[dict]) -> list[dict]:
    """Le journal lisible, le plus récent d'abord."""
    noms = {c["id"]: c["nom"] for c in fiche["coproprietaires"]}
    libelles = {"nom": "nom", "email": "adresse électronique", "telephone": "téléphone", "adresse": "adresse postale",
                "envoi": "canal d'envoi", "grands_caracteres": "grands caractères",
                "demande_papier": "demande de courrier", "aidant": "proche aidant"}
    res = []
    for m in reversed(j):
        if m["action"] == "coproprietaire_maj":
            quoi = f"{noms.get(m['id'], m['id'])} : " + ", ".join(libelles.get(k, k) for k in m["champs"])
        elif m["action"] == "coproprietaire_ajout":
            quoi = f"Nouveau copropriétaire : {m['coproprietaire']['nom']}"
        else:
            s = "s" if len(m["lots"]) > 1 else ""
            quoi = (f"Lot{s} {', '.join(map(str, m['lots']))} : {noms.get(m['ancien'], m['ancien'])} → "
                    f"{noms.get(m['nouveau'], m['nouveau'])}")
        res.append({"le": m["le"], "quoi": quoi, "motif": m.get("motif")})
    return res

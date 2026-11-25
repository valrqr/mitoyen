"""
api.py — Le moteur du syndic, exposé en petite API HTTP.

n8n (ou n'importe quel autre orchestrateur) appelle ces routes au lieu de lancer
des scripts. Le moteur ne fait que préparer : il n'envoie jamais rien lui-même.

Routes :
    GET  /sante                                             le moteur répond-il ?
    GET  /copros                                            fiches disponibles
    GET  /copros/{copro}/fiche                              validation + alertes de l'échéancier
    GET  /copros/{copro}/echeancier?au=&horizon=            échéances structurées d'une copro
    GET  /echeancier?au=&horizon=                           échéances de toutes les copros (workflow hebdo)
    POST /copros/{copro}/appels/{exercice}/T{n}?final=false génère avis + récap, renvoie la liste d'envoi
    GET  /copros/{copro}/appels/{exercice}/T{n}             relit la liste d'envoi déjà générée
    GET  /copros/{copro}/appels/{exercice}/T{n}/recap       PDF de la récap à valider
    GET  /copros/{copro}/appels/{exercice}/T{n}/avis/{id}   PDF d'un avis
    GET  /copros/{copro}/travaux                            dossiers de travaux
    POST /copros/{copro}/travaux                            créer un dossier (JSON)
    GET  /copros/{copro}/travaux/{id}                       dossier + comparatif + qui décide
    POST /copros/{copro}/travaux/{id}/devis                 ajouter un devis (formulaire + PDF)
    GET  /copros/{copro}/travaux/{id}/devis/{devis}/pdf     PDF d'un devis
    GET  /copros/{copro}/travaux/{id}/comparatif.pdf        comparatif à joindre ou diffuser
    POST /copros/{copro}/travaux/{id}/resume                résumé IA des devis (brouillon)
    PUT  /copros/{copro}/travaux/{id}/resume                le syndic valide (et corrige) le résumé
    POST /copros/{copro}/travaux/{id}/verifications         vérifie les entreprises (registre, BODACC, décennale)
    POST /copros/{copro}/travaux/{id}/sondages              ouvre un sondage consultatif, renvoie les liens personnels
    GET  /copros/{copro}/travaux/{id}/sondages/{s}          résultats du sondage
    POST /copros/{copro}/travaux/{id}/sondages/{s}/cloture  clôture anticipée
    POST /copros/{copro}/travaux/{id}/ag                    dépouillement d'AG (une résolution par devis)
    POST /copros/{copro}/travaux/{id}/conseil               vote du conseil syndical (délégation)
    GET  /copros/{copro}/plan                               plan de travaux, suivi, cotisation minimale, conformité
    GET  /copros/{copro}/plan/projection?cotisation=&indexation=   fonds de travaux sur 10 ans + quotes-parts
    GET  /copros/{copro}/plan.pdf?cotisation=&indexation=   projection à diffuser ou joindre à la convocation
    PUT  /copros/{copro}/plan/lignes/{ligne}                avancement d'une ligne (reportée, réalisée…)
    POST /copros/{copro}/plan/lignes/{ligne}/dossier        ouvre le dossier de travaux d'une ligne du plan
    GET  /copros/{copro}/ag                                 assemblées générales préparées
    GET  /copros/{copro}/ag/ordre-du-jour-type              résolutions habituelles d'une AG annuelle
    POST /copros/{copro}/ag                                 prépare une AG (date, lieu, ordre du jour)
    GET  /copros/{copro}/ag/{ag}                            AG + calendrier légal + feuille de présence
    GET  /copros/{copro}/ag/{ag}/formulaires/{id}           formulaire de vote par correspondance pré-rempli (PDF)
    PUT  /copros/{copro}/ag/{ag}/correspondance/{id}        enregistre un formulaire reçu (refusé hors délai)
    PUT  /copros/{copro}/ag/{ag}/presences                  présents, visio, mandats (contrôle de l'art. 22)
    GET  /copros/{copro}/ag/{ag}/feuille-presence.pdf       feuille de présence à faire émarger
    POST /copros/{copro}/ag/{ag}/depouillement              votes en séance + par correspondance → résultats
    GET  /copros/{copro}/ag/{ag}/pv.pdf                     brouillon de procès-verbal (filigrane PROJET)
    GET  /copros/{copro}/communication?au=                  canal de chaque copropriétaire (courrier, mail), aidants
    GET  /copros/{copro}/coproprietaires/{id}/mandat-sepa.pdf   mandat de prélèvement papier pré-rempli
    GET  /copros/{copro}/travaux/{id}/sondages/{s}/bulletins/{cp}   bulletin de sondage papier (PDF)
    POST /copros/{copro}/travaux/{id}/sondages/{s}/bulletins/{cp}   saisie d'un bulletin papier reçu
    GET  /copros/{copro}/affiche.pdf?format=A4|A3&au=       affiche du hall, sans donnée personnelle
    POST /copros/{copro}/appels/{exercice}/T{n}/lot-postal  PDF prêt à imprimer + manifeste des courriers
    GET  /copros/{copro}/envois?document=                   registre des envois (recommandés, notifications)
    POST /copros/{copro}/envois                             inscrit un envoi au registre
    PUT  /copros/{copro}/envois/{id}                        date de première présentation, statut, n° de recommandé
    GET  /copros/{copro}/ag/{ag}/convocations               chaque copropriétaire a-t-il été convoqué à temps ?
    POST /copros/{copro}/banque/releves                     import d'un relevé bancaire CSV (sans doublon)
    GET  /copros/{copro}/impayes?au=                        rapprochement, comptes, relances proposées
    GET  /copros/{copro}/impayes.pdf?au=                    état des impayés (document interne)
    PUT  /copros/{copro}/banque/operations/{op}             confirmer, ignorer ou annuler un rapprochement
    POST /copros/{copro}/impayes/ajustements                solde antérieur, appel de travaux, frais, avoir
    POST /copros/{copro}/relances/{cid}                     préparer la relance proposée (PDF)
    GET  /copros/{copro}/relances/{id}.pdf                  la lettre
    PUT  /copros/{copro}/relances/{id}                      marquer envoyée (date, moyen, présentation) ou annulée
    GET  /copros/{copro}/ag/{id}/agenda.ics                 « ajouter à mon calendrier »
    GET  /copros/{copro}/ag/{id}/rappels?au=                rappel du jour (J-7, J-1) pour une AG
    GET  /rappels-ag?au=                                    tous les rappels du jour, un par destinataire (n8n)
    GET  /copros/{copro}/meubles-tourisme?au=               registre des déclarations, interdiction possible ?
    POST /copros/{copro}/meubles-tourisme/declarations      information reçue d'un propriétaire (art. 9-2)
    PUT  /copros/{copro}/meubles-tourisme/declarations/{id} fin de la location touristique
    GET  /copros/{copro}/meubles-tourisme/affichage.pdf     affiche pour les parties communes
    GET  /copros/{copro}/meubles-tourisme/resolution        projet de résolution d'interdiction (art. 26 d)
    GET  /copros/{copro}/bienvenue/proprietaire.pdf?lots=&nom=  pack nouvel arrivant (guide, fiche synthétique, bulletin)
    GET  /copros/{copro}/bienvenue/locataire.pdf?lots=      pack locataire, remis par le bailleur
    GET  /copros/{copro}/fiche-synthetique?au=              fiche synthétique (décret 2016-1822), données manquantes
    GET  /copros/{copro}/fiche-synthetique.pdf?au=          la même, en PDF
    POST /copros/{copro}/ventes                             dossier de vente d'un ou plusieurs lots (bordereau, PDF, ZIP)
    GET  /copros/{copro}/ventes/{id}.zip                    archive du dossier, prête à transmettre au notaire
    POST /copros/{copro}/transmission                       dossier de transfert vers un autre syndic (ZIP, art. 18-2)
    GET  /vote/{copro}/{id}/{s}/{jeton}                     page de vote d'un copropriétaire (sans clé d'API)
    GET  /signaler/{copro}/{jeton}                          signaler un problème (lien du QR code du hall, sans clé)

Sécurité : chaque requête doit porter l'en-tête  X-API-Key: <MOTEUR_TOKEN>.
Lancement local : uvicorn moteur.api:app --reload   (depuis la racine du projet)
"""

from __future__ import annotations

import json
import hashlib
import os
import re
import secrets
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from typing import Literal

from fastapi import Depends, FastAPI, Request, File, Form, HTTPException, Path as PathParam, Query, Security, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.security import APIKeyHeader
from starlette.middleware.sessions import SessionMiddleware
from pydantic import BaseModel, Field

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "core"))
from avis_appel import FicheInvalide, dossier_appel, generer_appel  # noqa: E402
from fiche_copro import HORIZON_ALERTES_JOURS, alertes_echeancier, charger_fiche, echeances, valider  # noqa: E402
import ag as assemblee  # noqa: E402
import papier  # noqa: E402
import plan_travaux  # noqa: E402
import vente  # noqa: E402
import banque  # noqa: E402
import impayes  # noqa: E402
import compta  # noqa: E402
import annexes  # noqa: E402
import etat_date  # noqa: E402
import bulletin  # noqa: E402
import consultation  # noqa: E402
import rappel_ag  # noqa: E402
import reglement  # noqa: E402
import meubles_tourisme  # noqa: E402
import nouvel_arrivant  # noqa: E402
import resume_ia  # noqa: E402
import travaux  # noqa: E402
import transmission  # noqa: E402
import signalements  # noqa: E402
import vote  # noqa: E402

from . import page_vote  # noqa: E402
from . import page_signalement  # noqa: E402

DOSSIER_CONFIG = Path(os.getenv("MOTEUR_CONFIG_DIR", RACINE / "config"))
DOSSIER_SORTIE = Path(os.getenv("MOTEUR_OUT_DIR", RACINE / "out"))
DOSSIER_DATA = Path(os.getenv("MOTEUR_DATA_DIR", RACINE / "data"))   # dossiers de travaux, devis
TOKEN = os.getenv("MOTEUR_TOKEN", "")
URL_PUBLIQUE = os.getenv("MOTEUR_URL_PUBLIQUE", "http://localhost:8000").rstrip("/")

# Identifiants autorisés : lettres, chiffres, tirets. Empêche de sortir des dossiers (../).
SLUG = r"^[a-z0-9][a-z0-9-]{0,40}$"
ID_COPRO = r"^[A-Za-z0-9_-]{1,20}$"
ID_DOSSIER = r"^\d{4}-\d{3}-[a-z0-9-]{1,40}$"
ID_DEVIS = r"^D\d{1,3}$"
ID_SONDAGE = r"^S\d{1,3}$"

# Interface web : une session signée (cookie) remplace la clé d'API pour le navigateur.
# SameSite=Lax : le cookie n'accompagne pas un formulaire posté depuis un autre site.
SECRET_SESSION = os.getenv("INTERFACE_SECRET") or (
    hashlib.sha256(f"mitoyen-interface:{TOKEN}".encode()).hexdigest() if TOKEN else secrets.token_hex(32))

app = FastAPI(title="Moteur syndic IA", version="0.1.0",
              description="Prépare les documents du syndic. Le syndic valide, n8n envoie.")
app.add_middleware(SessionMiddleware, secret_key=SECRET_SESSION, session_cookie="mitoyen_session",
                   max_age=8 * 3600, same_site="lax", https_only=os.getenv("INTERFACE_HTTPS", "") == "1")


cle_api = APIKeyHeader(name="X-API-Key", auto_error=False,
                       description="La valeur de MOTEUR_TOKEN (fichier .env)")


def verifier_cle(request: Request, x_api_key: str | None = Security(cle_api)) -> None:
    if request.session.get("syndic"):          # connecté à l'interface web
        return
    if not TOKEN:
        raise HTTPException(500, "MOTEUR_TOKEN n'est pas défini côté moteur")
    if x_api_key != TOKEN:
        raise HTTPException(401, "Clé d'API invalide ou absente (en-tête X-API-Key)")


def fiche_de(copro: str) -> dict:
    chemin = DOSSIER_CONFIG / f"{copro}.yaml"
    if not chemin.is_file():
        raise HTTPException(404, f"Aucune fiche pour la copro « {copro} »")
    return charger_fiche(chemin)


def verifier_exercice(fiche: dict, exercice: int) -> None:
    attendu = fiche["budget_previsionnel"]["exercice"]
    if exercice != attendu:
        raise HTTPException(409, f"La fiche porte sur l'exercice {attendu}, pas {exercice}")


Copro = PathParam(..., pattern=SLUG)
Trimestre = PathParam(..., ge=1, le=4)


# --------------------------------------------------------------------------- #
@app.get("/sante")
def sante() -> dict:
    return {"statut": "ok"}


@app.get("/copros", dependencies=[Depends(verifier_cle)])
def lister_copros() -> list[str]:
    return sorted(p.stem for p in DOSSIER_CONFIG.glob("*.yaml"))


@app.get("/copros/{copro}/fiche", dependencies=[Depends(verifier_cle)])
def controler_fiche(copro: str = Copro, au: date | None = Query(None, description="Date de référence")) -> dict:
    fiche = fiche_de(copro)
    rapport = valider(fiche)
    return {"copro": copro, "valide": rapport.ok, "erreurs": rapport.erreurs,
            "alertes": alertes_echeancier(fiche, au or date.today())}


def rapport_echeancier(copro: str, fiche: dict, au: date, horizon: int) -> dict:
    gouv = fiche["gouvernance"]
    sid = gouv["syndic"]["coproprietaire_id"]
    syndic = next((c for c in fiche["coproprietaires"] if c["id"] == sid), {})
    alertes = echeances(fiche, au, horizon, plan_travaux.charger_suivi(DOSSIER_DATA, copro))
    alertes += alertes_impayes(copro, fiche, au)
    return {
        "copro": copro, "copropriete": fiche["copropriete"]["nom"],
        "au": au.isoformat(), "au_fr": f"{au:%d/%m/%Y}", "horizon_jours": horizon,
        "syndic": {"nom": syndic.get("nom"), "email": syndic.get("email")},
        "nb_alertes": len(alertes),
        "nb_urgentes": sum(1 for a in alertes if a["niveau"] == "urgent"),
        "alertes": alertes,
    }


def alertes_impayes(copro: str, fiche: dict, au: date) -> list[dict]:
    """Relances à préparer, paiements à confirmer et délais 19-2 expirés, pour l'échéancier."""
    if not banque.charger_operations(DOSSIER_DATA, copro):
        return []
    from fiche_copro import _alerte
    e = impayes.etat(fiche, DOSSIER_SORTIE, DOSSIER_DATA, copro, au)
    res = []
    n = sum(1 for p in e["relances"] if p["etat"] == "a_preparer")
    if n:
        res.append(_alerte("impayes", f"{n} relance(s) à préparer",
                           "Impayés : relances proposées par Mitoyen, à relire avant envoi.", au, au, "urgent"))
    if e["a_confirmer"]:
        res.append(_alerte("impayes", f"{len(e['a_confirmer'])} paiement(s) à confirmer",
                           "Opérations du relevé rattachées par le nom ou le montant : à vérifier.", au, au, "important"))
    for p in e["relances"]:
        if p["etat"] == "delai_expire":
            res.append(_alerte("impayes", f"Mise en demeure sans effet : {p['nom']}", p["message"],
                               date.fromisoformat(p["date_limite"]), au, "urgent"))
    return res


Horizon = Query(HORIZON_ALERTES_JOURS, ge=1, le=730, description="Nombre de jours à anticiper")


@app.get("/copros/{copro}/echeancier", dependencies=[Depends(verifier_cle)])
def echeancier_copro(copro: str = Copro, au: date | None = Query(None), horizon: int = Horizon) -> dict:
    return rapport_echeancier(copro, fiche_de(copro), au or date.today(), horizon)


@app.get("/echeancier", dependencies=[Depends(verifier_cle)])
def echeancier_global(au: date | None = Query(None), horizon: int = Horizon) -> dict:
    """Une entrée par copro, pour le récapitulatif hebdomadaire envoyé à chaque syndic."""
    jour = au or date.today()
    rapports = [rapport_echeancier(c, fiche_de(c), jour, horizon) for c in lister_copros()]
    return {"au": jour.isoformat(), "nb_copros": len(rapports), "rapports": rapports}


@app.post("/copros/{copro}/appels/{exercice}/T{trimestre}", dependencies=[Depends(verifier_cle)])
def generer(copro: str = Copro, exercice: int = PathParam(...), trimestre: int = Trimestre,
            final: bool = Query(False, description="true = sans filigrane PROJET, après validation")) -> dict:
    fiche = fiche_de(copro)
    verifier_exercice(fiche, exercice)
    try:
        return generer_appel(fiche, copro, trimestre, DOSSIER_SORTIE, final)
    except FicheInvalide as e:
        raise HTTPException(422, {"message": "Fiche invalide, aucun avis généré", "erreurs": e.erreurs})


def dossier_existant(copro: str, exercice: int, trimestre: int) -> Path:
    d = dossier_appel(DOSSIER_SORTIE, copro, exercice, trimestre)
    if not (d / "envoi.json").is_file():
        raise HTTPException(404, "Appel pas encore généré : appelez d'abord la route POST")
    return d


@app.get("/copros/{copro}/appels/{exercice}/T{trimestre}", dependencies=[Depends(verifier_cle)])
def relire(copro: str = Copro, exercice: int = PathParam(...), trimestre: int = Trimestre) -> dict:
    d = dossier_existant(copro, exercice, trimestre)
    return json.loads((d / "envoi.json").read_text(encoding="utf-8"))


@app.get("/copros/{copro}/appels/{exercice}/T{trimestre}/recap", dependencies=[Depends(verifier_cle)])
def recap(copro: str = Copro, exercice: int = PathParam(...), trimestre: int = Trimestre) -> FileResponse:
    d = dossier_existant(copro, exercice, trimestre)
    return FileResponse(d / "recap_syndic.pdf", media_type="application/pdf", filename="recap_syndic.pdf")


@app.get("/copros/{copro}/appels/{exercice}/T{trimestre}/avis/{cid}", dependencies=[Depends(verifier_cle)])
def avis(copro: str = Copro, exercice: int = PathParam(...), trimestre: int = Trimestre,
         cid: str = PathParam(..., pattern=ID_COPRO)) -> FileResponse:
    d = dossier_existant(copro, exercice, trimestre)
    fichier = d / f"avis_{cid}.pdf"
    if not fichier.is_file():
        raise HTTPException(404, f"Pas d'avis pour {cid}")
    return FileResponse(fichier, media_type="application/pdf", filename=fichier.name)


# --------------------------------------------------------------------------- #
# Travaux et devis
# --------------------------------------------------------------------------- #
class NouveauDossier(BaseModel):
    titre: str = Field(..., min_length=3, max_length=120, examples=["Remplacement de la porte du garage"])
    description: str = Field("", max_length=4000)
    nature: str = Field("reparation", description="entretien | reparation | amelioration")
    urgence: bool = False
    cle: str = Field("generales", description="Clé de répartition de la fiche")


def _json(v):
    """Montants en texte (« 3058.00 ») : jamais de flottant pour de l'argent."""
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, dict):
        return {k: _json(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_json(x) for x in v]
    return v


Dossier = PathParam(..., pattern=ID_DOSSIER)


def dossier_de(copro: str, dossier_id: str) -> tuple[Path, dict]:
    chemin = travaux.dossier_dir(DOSSIER_DATA, copro, dossier_id)
    if not (chemin / "dossier.yaml").is_file():
        raise HTTPException(404, f"Aucun dossier de travaux « {dossier_id} »")
    return chemin, travaux.charger_dossier(chemin)


@app.get("/copros/{copro}/travaux", dependencies=[Depends(verifier_cle)])
def lister_travaux(copro: str = Copro) -> list[dict]:
    fiche_de(copro)
    return travaux.lister_dossiers(DOSSIER_DATA, copro)


@app.post("/copros/{copro}/travaux", status_code=201, dependencies=[Depends(verifier_cle)])
def creer_travaux(corps: NouveauDossier, copro: str = Copro) -> dict:
    try:
        return travaux.creer_dossier(DOSSIER_DATA, copro, fiche_de(copro), corps.titre, corps.description,
                                     corps.nature, corps.urgence, corps.cle)
    except travaux.DossierInvalide as e:
        raise HTTPException(422, str(e))


@app.get("/copros/{copro}/travaux/{dossier_id}", dependencies=[Depends(verifier_cle)])
def voir_travaux(copro: str = Copro, dossier_id: str = Dossier, au: date | None = Query(None)) -> dict:
    _, d = dossier_de(copro, dossier_id)
    return _json(travaux.synthese(fiche_de(copro), d, au))


@app.post("/copros/{copro}/travaux/{dossier_id}/devis", status_code=201, dependencies=[Depends(verifier_cle)])
async def ajouter_devis(copro: str = Copro, dossier_id: str = Dossier,
                        entreprise: str = Form(..., max_length=120),
                        montant_ht: str = Form(..., description="Montant hors taxes, ex. 2780 ou 2 780,50"),
                        taux_tva: str = Form("10", description="5.5, 10 ou 20"),
                        delai_jours: int | None = Form(None, ge=0, le=3650),
                        valide_jusqu_au: date | None = Form(None),
                        remarques: str = Form("", max_length=2000),
                        fichier: UploadFile | None = File(None, description="Le devis en PDF (10 Mo max)")) -> dict:
    fiche_de(copro)
    _, d = dossier_de(copro, dossier_id)
    pdf = None
    if fichier is not None and fichier.filename:
        pdf = await fichier.read(travaux.TAILLE_MAX_PDF + 1)
    try:
        devis = travaux.ajouter_devis(DOSSIER_DATA, copro, d, entreprise, montant_ht, taux_tva,
                                      delai_jours, valide_jusqu_au, remarques, pdf)
    except travaux.DossierInvalide as e:
        raise HTTPException(422, str(e))
    return _json(devis)


@app.get("/copros/{copro}/travaux/{dossier_id}/devis/{devis_id}/pdf", dependencies=[Depends(verifier_cle)])
def pdf_devis(copro: str = Copro, dossier_id: str = Dossier,
              devis_id: str = PathParam(..., pattern=ID_DEVIS)) -> FileResponse:
    chemin, d = dossier_de(copro, dossier_id)
    devis = next((x for x in d["devis"] if x["id"] == devis_id), None)
    if not devis or not devis.get("fichier"):
        raise HTTPException(404, f"Pas de PDF pour le devis {devis_id}")
    return FileResponse(chemin / devis["fichier"], media_type="application/pdf",
                        filename=f"{dossier_id}_{devis_id}.pdf")


@app.get("/copros/{copro}/travaux/{dossier_id}/comparatif.pdf", dependencies=[Depends(verifier_cle)])
def pdf_comparatif(copro: str = Copro, dossier_id: str = Dossier, au: date | None = Query(None)) -> FileResponse:
    chemin, d = dossier_de(copro, dossier_id)
    if not d["devis"]:
        raise HTTPException(409, "Ajoutez au moins un devis avant de générer le comparatif")
    fiche = fiche_de(copro)
    sortie = travaux.generer_pdf(fiche, travaux.synthese(fiche, d, au), chemin / "comparatif.pdf", au)
    return FileResponse(sortie, media_type="application/pdf", filename=f"comparatif_{dossier_id}.pdf")


class ValidationResume(BaseModel):
    texte: str | None = Field(None, max_length=1500, description="Texte corrigé par le syndic (facultatif)")


@app.post("/copros/{copro}/travaux/{dossier_id}/resume", status_code=201, dependencies=[Depends(verifier_cle)])
def generer_resume(copro: str = Copro, dossier_id: str = Dossier, au: date | None = Query(None)) -> dict:
    chemin, d = dossier_de(copro, dossier_id)
    fiche = fiche_de(copro)
    comp = travaux.comparatif(fiche, d, au)
    try:
        resume = resume_ia.generer(fiche, d, comp, chemin)
    except ValueError as e:
        raise HTTPException(409, str(e))
    except resume_ia.IAIndisponible as e:
        raise HTTPException(503, str(e))
    d["resume_ia"] = resume
    travaux.sauver_dossier(chemin, d)
    return resume_ia.etat(resume, d)


@app.put("/copros/{copro}/travaux/{dossier_id}/resume", dependencies=[Depends(verifier_cle)])
def valider_resume(corps: ValidationResume, copro: str = Copro, dossier_id: str = Dossier) -> dict:
    chemin, d = dossier_de(copro, dossier_id)
    actuel = resume_ia.etat(d.get("resume_ia"), d)
    if not actuel:
        raise HTTPException(404, "Aucun résumé à valider : générez-le d'abord")
    if actuel["obsolete"]:
        raise HTTPException(409, "Les devis ont changé depuis le résumé : générez-en un nouveau")
    try:
        d["resume_ia"] = resume_ia.valider(d["resume_ia"], corps.texte, comp=travaux.comparatif(fiche_de(copro), d))
    except ValueError as e:
        raise HTTPException(422, str(e))
    travaux.sauver_dossier(chemin, d)
    return resume_ia.etat(d["resume_ia"], d)


class DemandeVerification(BaseModel):
    siren: dict[str, str] = Field(default_factory=dict,
                                  description="SIREN saisis à la main quand le devis n'en porte pas, ex. {\"D2\": \"123456789\"}")


@app.post("/copros/{copro}/travaux/{dossier_id}/verifications", dependencies=[Depends(verifier_cle)])
def verifier_entreprises(corps: DemandeVerification | None = None, copro: str = Copro,
                         dossier_id: str = Dossier) -> list[dict]:
    fiche_de(copro)
    _, d = dossier_de(copro, dossier_id)
    if not d["devis"]:
        raise HTTPException(409, "Ajoutez au moins un devis avant de vérifier les entreprises")
    try:
        return travaux.verifier_entreprises(DOSSIER_DATA, copro, d, (corps.siren if corps else None))
    except travaux.DossierInvalide as e:
        raise HTTPException(422, str(e))


# --------------------------------------------------------------------------- #
# Plan pluriannuel de travaux
# --------------------------------------------------------------------------- #
ID_LIGNE = r"^L\d{1,3}$"
Ligne = PathParam(..., pattern=ID_LIGNE)
Cotisation = Query(None, ge=0, le=1_000_000, description="Cotisation annuelle à simuler (défaut : celle de la fiche)")
Indexation = Query(0, ge=0, le=20, description="Hausse annuelle des prix, en % (ex. 3)")


def plan_de(copro: str) -> tuple[dict, dict]:
    fiche = fiche_de(copro)
    if not plan_travaux.plan_de(fiche):
        raise HTTPException(404, f"La fiche « {copro} » ne contient pas de plan de travaux")
    erreurs = plan_travaux.valider_plan(fiche)
    if erreurs:
        raise HTTPException(422, {"message": "Plan de travaux invalide", "erreurs": erreurs})
    return fiche, plan_travaux.charger_suivi(DOSSIER_DATA, copro)


@app.get("/copros/{copro}/plan", dependencies=[Depends(verifier_cle)])
def voir_plan(copro: str = Copro, au: date | None = Query(None)) -> dict:
    fiche, suivi = plan_de(copro)
    p = plan_travaux.plan_de(fiche)
    return _json({
        "copro": copro, "statut": p["statut"], "elabore_le": p["elabore_le"].isoformat(),
        "elabore_par": p.get("elabore_par"),
        "adopte_le": p["adopte_le"].isoformat() if p.get("adopte_le") else None,
        "lignes": plan_travaux.lignes(fiche, suivi),
        "cotisation_minimale": plan_travaux.cotisation_minimale(fiche),
        "conformite": plan_travaux.conformite(fiche, au or date.today(), suivi),
    })


@app.get("/copros/{copro}/plan/projection", dependencies=[Depends(verifier_cle)])
def projeter_plan(copro: str = Copro, cotisation: Decimal | None = Cotisation,
                  indexation: Decimal = Indexation) -> dict:
    fiche, suivi = plan_de(copro)
    proj = plan_travaux.projection(fiche, suivi, cotisation, indexation)
    lissage = plan_travaux.cotisation_lissee(fiche, suivi, indexation)
    cmin = plan_travaux.cotisation_minimale(fiche)
    qp = plan_travaux.quotes_parts(fiche, proj)
    for q in qp:   # clés JSON en texte
        q["annees"] = {str(an): v for an, v in q["annees"].items()}
    return _json({"en_bref": plan_travaux.en_bref(fiche, proj, lissage, cmin), "projection": proj,
                  "cotisation_lissee": lissage, "cotisation_minimale": cmin, "quotes_parts": qp})


@app.get("/copros/{copro}/plan.pdf", dependencies=[Depends(verifier_cle)])
def pdf_plan(copro: str = Copro, cotisation: Decimal | None = Cotisation, indexation: Decimal = Indexation,
             au: date | None = Query(None)) -> FileResponse:
    fiche, suivi = plan_de(copro)
    sortie = DOSSIER_SORTIE / copro / "plan"
    sortie.mkdir(parents=True, exist_ok=True)
    jour = au or date.today()
    chemin = plan_travaux.generer_pdf(fiche, sortie / f"plan_travaux_{jour:%Y%m%d}.pdf", suivi, cotisation,
                                      indexation, jour)
    return FileResponse(chemin, media_type="application/pdf", filename=chemin.name)


class SuiviLigne(BaseModel):
    statut: str = Field(..., description="prevu | engage | realise | reporte | abandonne")
    annee: int | None = Field(None, ge=2000, le=2100, description="Nouvelle année (obligatoire pour un report)")
    montant_reel: Decimal | None = Field(None, gt=0, description="Montant payé (obligatoire si réalisé)")
    note: str = Field("", max_length=500)


@app.put("/copros/{copro}/plan/lignes/{ligne}", dependencies=[Depends(verifier_cle)])
def suivre_ligne(corps: SuiviLigne, copro: str = Copro, ligne: str = Ligne) -> dict:
    fiche, _ = plan_de(copro)
    try:
        return _json(plan_travaux.mettre_a_jour_ligne(DOSSIER_DATA, copro, fiche, ligne, corps.statut, corps.annee,
                                                      corps.montant_reel, corps.note))
    except plan_travaux.PlanInvalide as e:
        raise HTTPException(422, str(e))


@app.post("/copros/{copro}/plan/lignes/{ligne}/dossier", status_code=201, dependencies=[Depends(verifier_cle)])
def ouvrir_dossier_plan(copro: str = Copro, ligne: str = Ligne) -> dict:
    fiche, _ = plan_de(copro)
    try:
        return plan_travaux.ouvrir_dossier(DOSSIER_DATA, copro, fiche, ligne)
    except (plan_travaux.PlanInvalide, travaux.DossierInvalide) as e:
        raise HTTPException(409 if "déjà" in str(e) else 422, str(e))


# --------------------------------------------------------------------------- #
# Assemblée générale sans papier
# --------------------------------------------------------------------------- #
ID_AG = r"^\d{4}-\d{2}-\d{2}(-[a-z0-9-]{1,30})?$"
ID_COPROPRIETAIRE = r"^[A-Za-z0-9_-]{1,20}$"
AgId = PathParam(..., pattern=ID_AG)
Coproprietaire = PathParam(..., pattern=ID_COPROPRIETAIRE)


class ResolutionAG(BaseModel):
    titre: str = Field(..., min_length=3, max_length=200)
    texte: str = Field("", max_length=4000)
    majorite: str = Field("24", description="24 | 25 | 26 | info (point d'information, sans vote)")
    cle: str = Field("generales", description="Clé de répartition : seuls les copropriétaires concernés votent")


class NouvelleAG(BaseModel):
    date: date
    heure: str = Field(..., max_length=20, examples=["18h30"])
    lieu: str = Field(..., min_length=3, max_length=200)
    titre: str = Field("Assemblée générale ordinaire", max_length=120)
    annuelle: bool = True
    visio: str | None = Field(None, max_length=300, description="Moyens de visio décidés par une AG précédente")
    suffixe: str = Field("", pattern=r"^[a-z0-9-]{0,30}$", description="Pour distinguer deux AG le même jour")
    resolutions: list[ResolutionAG] = Field(default_factory=list)
    dossiers: list[str] = Field(default_factory=list, description="Dossiers de travaux : une résolution par devis")


def ag_de(copro: str, ag_id: str) -> dict:
    try:
        return assemblee.charger_ag(DOSSIER_DATA, copro, ag_id)
    except (FileNotFoundError, assemblee.AGInvalide):
        raise HTTPException(404, f"Aucune AG « {ag_id} »")


@app.get("/copros/{copro}/ag", dependencies=[Depends(verifier_cle)])
def lister_ag(copro: str = Copro) -> list[dict]:
    fiche_de(copro)
    return assemblee.lister_ag(DOSSIER_DATA, copro)


@app.get("/copros/{copro}/ag/ordre-du-jour-type", dependencies=[Depends(verifier_cle)])
def odj_type(copro: str = Copro) -> dict:
    fiche = fiche_de(copro)
    adopte = (plan_travaux.plan_de(fiche) or {}).get("statut") == "adopte"
    return {"resolutions": assemblee.ordre_du_jour_type(fiche, adopte),
            "avertissement": "Majorités usuelles, à vérifier selon le règlement de copropriété et auprès de l'ADIL."}


@app.post("/copros/{copro}/ag", status_code=201, dependencies=[Depends(verifier_cle)])
def creer_ag(corps: NouvelleAG, copro: str = Copro) -> dict:
    fiche = fiche_de(copro)
    try:
        rappel_ag.heure_de(corps.heure)          # l'heure doit être lisible (rappels, agenda)
    except rappel_ag.RappelInvalide as e:
        raise HTTPException(422, str(e))
    resolutions = [r.model_dump() for r in corps.resolutions]
    for did in corps.dossiers:
        _, d = dossier_de(copro, did) if re.match(ID_DOSSIER, did) else (None, None)
        if d is None:
            raise HTTPException(422, f"Dossier de travaux invalide : {did}")
        resolutions += assemblee.resolutions_depuis_dossier(d)
    # Art. 9-2 : un point d'information sur les meublés de tourisme déclarés depuis la dernière AG
    point_mt = meubles_tourisme.point_information(fiche, meubles_tourisme.charger(DOSSIER_DATA, copro), corps.date)
    if point_mt:
        resolutions.append({k: v for k, v in point_mt.items() if not k.startswith("_")})
    try:
        a = assemblee.creer_ag(DOSSIER_DATA, copro, fiche, corps.date, corps.heure, corps.lieu, resolutions,
                               corps.titre, corps.annuelle, corps.visio, corps.suffixe)
    except assemblee.AGInvalide as e:
        raise HTTPException(422, str(e))
    ajouts = []
    if point_mt:
        meubles_tourisme.marquer_inscrites(DOSSIER_DATA, copro, point_mt["_declarations"], a["id"])
        ajouts.append("Point d'information sur les meublés de tourisme (loi 1965, art. 9-2), ajouté automatiquement")
    return {**a, "calendrier": assemblee.calendrier(fiche, a), "points_ajoutes": ajouts}


@app.get("/copros/{copro}/ag/{ag_id}", dependencies=[Depends(verifier_cle)])
def voir_ag(copro: str = Copro, ag_id: str = AgId, au: date | None = Query(None)) -> dict:
    fiche, a = fiche_de(copro), ag_de(copro, ag_id)
    return {**a, "calendrier": assemblee.calendrier(fiche, a, au), "feuille": assemblee.feuille_presence(fiche, a)}


@app.get("/copros/{copro}/ag/{ag_id}/formulaires/{cid}", dependencies=[Depends(verifier_cle)])
def formulaire_vpc(copro: str = Copro, ag_id: str = AgId, cid: str = Coproprietaire) -> FileResponse:
    fiche, a = fiche_de(copro), ag_de(copro, ag_id)
    sortie = DOSSIER_SORTIE / copro / "ag" / ag_id
    sortie.mkdir(parents=True, exist_ok=True)
    try:
        chemin = assemblee.generer_formulaire(fiche, a, cid, sortie / f"formulaire_vote_{cid}.pdf")
    except assemblee.AGInvalide as e:
        raise HTTPException(404, str(e))
    return FileResponse(chemin, media_type="application/pdf", filename=chemin.name)


class FormulaireRecu(BaseModel):
    votes: dict[str, str | None] = Field(..., description="{numéro de résolution: pour | contre | abstention | null}")
    recu_le: date
    mode: str = Field("courrier", description="courrier | email | main_propre")


@app.put("/copros/{copro}/ag/{ag_id}/correspondance/{cid}", dependencies=[Depends(verifier_cle)])
def recevoir_formulaire(corps: FormulaireRecu, copro: str = Copro, ag_id: str = AgId,
                        cid: str = Coproprietaire) -> dict:
    fiche, a = fiche_de(copro), ag_de(copro, ag_id)
    try:
        f = assemblee.enregistrer_correspondance(fiche, a, cid, corps.votes, corps.recu_le, corps.mode)
    except (assemblee.AGInvalide, ValueError) as e:
        raise HTTPException(422, str(e))
    assemblee.sauver_ag(DOSSIER_DATA, copro, a)
    return {"coproprietaire": cid, **f}


class Presences(BaseModel):
    presences: dict[str, dict] = Field(..., description='{"CP06": {"mode": "represente", "mandataire": "CP07"}}')


@app.put("/copros/{copro}/ag/{ag_id}/presences", dependencies=[Depends(verifier_cle)])
def enregistrer_presences(corps: Presences, copro: str = Copro, ag_id: str = AgId) -> dict:
    fiche, a = fiche_de(copro), ag_de(copro, ag_id)
    try:
        remarques = assemblee.enregistrer_presences(fiche, a, corps.presences)
    except assemblee.AGInvalide as e:
        raise HTTPException(422, str(e))
    assemblee.sauver_ag(DOSSIER_DATA, copro, a)
    return {"remarques": remarques, "feuille": assemblee.feuille_presence(fiche, a)}


@app.get("/copros/{copro}/ag/{ag_id}/feuille-presence.pdf", dependencies=[Depends(verifier_cle)])
def pdf_presence(copro: str = Copro, ag_id: str = AgId) -> FileResponse:
    fiche, a = fiche_de(copro), ag_de(copro, ag_id)
    sortie = DOSSIER_SORTIE / copro / "ag" / ag_id
    sortie.mkdir(parents=True, exist_ok=True)
    chemin = assemblee.generer_feuille_presence(fiche, a, sortie / "feuille_presence.pdf")
    return FileResponse(chemin, media_type="application/pdf", filename=chemin.name)


class Seance(BaseModel):
    votes: dict[str, dict] = Field(default_factory=dict,
                                   description='{"2": {"contre": ["CP14"], "abstention": ["CP02"]}} : '
                                               'les autres participants en séance votent pour')
    amendees: list[int] = Field(default_factory=list, description="Résolutions amendées pendant la séance")


@app.post("/copros/{copro}/ag/{ag_id}/depouillement", dependencies=[Depends(verifier_cle)])
def depouiller_ag_complete(corps: Seance, copro: str = Copro, ag_id: str = AgId) -> dict:
    fiche, a = fiche_de(copro), ag_de(copro, ag_id)
    try:
        dep = assemblee.depouiller(fiche, a, corps.votes, corps.amendees)
    except (assemblee.AGInvalide, ValueError) as e:
        raise HTTPException(422, str(e))
    a["depouillement"] = {"votes": corps.votes, "amendees": corps.amendees, "le": date.today().isoformat()}
    assemblee.sauver_ag(DOSSIER_DATA, copro, a)
    return dep


@app.get("/copros/{copro}/ag/{ag_id}/pv.pdf", dependencies=[Depends(verifier_cle)])
def pdf_pv(copro: str = Copro, ag_id: str = AgId) -> FileResponse:
    fiche, a = fiche_de(copro), ag_de(copro, ag_id)
    if not a.get("depouillement"):
        raise HTTPException(409, "Le dépouillement n'a pas encore été fait (POST …/depouillement)")
    dep = assemblee.depouiller(fiche, a, a["depouillement"]["votes"], a["depouillement"]["amendees"])
    sortie = DOSSIER_SORTIE / copro / "ag" / ag_id
    sortie.mkdir(parents=True, exist_ok=True)
    chemin = assemblee.generer_pv(fiche, a, dep, sortie / "proces_verbal_projet.pdf")
    return FileResponse(chemin, media_type="application/pdf", filename=chemin.name)


# --------------------------------------------------------------------------- #
# Pack papier : courrier, grands caractères, bulletins, affiche, registre des envois
# --------------------------------------------------------------------------- #
def _pdf(chemin: Path) -> FileResponse:
    return FileResponse(chemin, media_type="application/pdf", filename=chemin.name)


@app.get("/copros/{copro}/communication", dependencies=[Depends(verifier_cle)])
def communication(copro: str = Copro, au: date | None = Query(None)) -> dict:
    fiche = fiche_de(copro)
    jour = au or date.today()
    lignes = []
    for c in sorted(fiche["coproprietaires"], key=lambda c: c["nom"]):
        k = papier.canal(fiche, c["id"], jour)
        lignes.append({"id": c["id"], "nom": c["nom"], **k, "grands_caracteres": bool(c.get("grands_caracteres")),
                       "paiement": c.get("paiement", "virement"),
                       "adresse_postale": papier.adresse_postale(fiche, c["id"]) if k["canal"] == "courrier" else None,
                       "aidant": (papier.copie_aidant(fiche, c["id"]) or {}).get("nom")})
    return {"au": jour.isoformat(), "nb_courrier": sum(1 for l in lignes if l["canal"] == "courrier"),
            "coproprietaires": lignes, "mention_obligatoire": papier.MENTION_PAPIER}


@app.get("/copros/{copro}/coproprietaires/{cid}/mandat-sepa.pdf", dependencies=[Depends(verifier_cle)])
def mandat_sepa(copro: str = Copro, cid: str = Coproprietaire) -> FileResponse:
    fiche = fiche_de(copro)
    sortie = DOSSIER_SORTIE / copro / "papier"
    sortie.mkdir(parents=True, exist_ok=True)
    try:
        return _pdf(papier.generer_mandat_sepa(fiche, cid, sortie / f"mandat_sepa_{cid}.pdf"))
    except papier.PapierInvalide as e:
        raise HTTPException(404 if "inconnu" in str(e) else 422, str(e))


@app.get("/copros/{copro}/travaux/{dossier_id}/sondages/{sid}/bulletins/{cid}", dependencies=[Depends(verifier_cle)])
def bulletin_papier(copro: str = Copro, dossier_id: str = Dossier, sid: str = PathParam(..., pattern=ID_SONDAGE),
                    cid: str = Coproprietaire) -> FileResponse:
    _, d = dossier_de(copro, dossier_id)
    fiche, s = fiche_de(copro), _sondage_de(d, sid)
    synth = travaux.synthese(fiche, d)
    sortie = DOSSIER_SORTIE / copro / "papier" / dossier_id
    sortie.mkdir(parents=True, exist_ok=True)
    try:
        return _pdf(papier.generer_bulletin(fiche, d, s, cid, synth["comparatif"], synth["resume_ia"],
                                           sortie / f"bulletin_{sid}_{cid}.pdf"))
    except papier.PapierInvalide as e:
        raise HTTPException(404, str(e))


class BulletinRecu(BaseModel):
    choix: str = Field(..., description="Identifiant du devis (D1…), aucun ou sans_avis")
    recu_le: datetime = Field(..., description="Date et heure de réception du bulletin par le syndic")


@app.post("/copros/{copro}/travaux/{dossier_id}/sondages/{sid}/bulletins/{cid}", dependencies=[Depends(verifier_cle)])
def saisir_bulletin(corps: BulletinRecu, copro: str = Copro, dossier_id: str = Dossier,
                    sid: str = PathParam(..., pattern=ID_SONDAGE), cid: str = Coproprietaire) -> dict:
    chemin, d = dossier_de(copro, dossier_id)
    s = _sondage_de(d, sid)
    try:
        res = papier.saisir_bulletin(s, cid, corps.choix, corps.recu_le.replace(tzinfo=None))
    except papier.PapierInvalide as e:
        raise HTTPException(422, str(e))
    travaux.sauver_dossier(chemin, d)
    return res


@app.get("/copros/{copro}/affiche.pdf", dependencies=[Depends(verifier_cle)])
def affiche(copro: str = Copro, format: str = Query("A4", pattern="^A[34]$"), au: date | None = Query(None)) -> FileResponse:
    fiche = fiche_de(copro)
    jour = au or date.today()
    sortie = DOSSIER_SORTIE / copro / "papier"
    sortie.mkdir(parents=True, exist_ok=True)
    return _pdf(papier.generer_affiche(fiche, DOSSIER_DATA, copro, sortie / f"affiche_{jour:%Y-%m}_{format}.pdf",
                                       jour, format))


@app.post("/copros/{copro}/appels/{exercice}/T{trimestre}/lot-postal", dependencies=[Depends(verifier_cle)])
def lot_postal(copro: str = Copro, exercice: int = PathParam(...), trimestre: int = Trimestre) -> dict:
    fiche = fiche_de(copro)
    dossier = dossier_existant(copro, exercice, trimestre)
    envoi = json.loads((dossier / "envoi.json").read_text(encoding="utf-8"))
    if envoi["statut"] != "valide":
        raise HTTPException(409, "Les avis sont encore en projet : générez la version finale avant de les poster")
    courriers = [{"coproprietaire": a["coproprietaire"], "fichiers": [dossier / a["fichier"]]}
                 for a in envoi["avis"] if a["envoi"] == "courrier"]
    if not courriers:
        return {"nb_courriers": 0, "note": "Aucun copropriétaire ne reçoit ses documents par courrier."}
    return papier.preparer_lot(fiche, courriers, dossier / "lot_postal", f"Appel de fonds {exercice}, appel {trimestre}",
                               f"appel:{exercice}-T{trimestre}", DOSSIER_DATA, copro)


class NouvelEnvoi(BaseModel):
    coproprietaire: str = Field(..., pattern=ID_COPROPRIETAIRE)
    document: str = Field(..., min_length=3, max_length=80, examples=["ag:2027-04-17", "appel:2027-T1"])
    canal: str = Field(..., description="lrar | lre | main_propre | courrier_simple | email")
    envoye_le: date
    numero: str = Field("", max_length=40, description="Numéro de recommandé")
    notifie_le: date | None = Field(None, description="Première présentation, ou remise contre émargement")
    note: str = Field("", max_length=300)


class MajEnvoi(BaseModel):
    statut: str | None = Field(None, description="prepare | envoye | notifie | retourne | refuse")
    notifie_le: date | None = None
    numero: str | None = Field(None, max_length=40)
    note: str | None = Field(None, max_length=300)


@app.get("/copros/{copro}/envois", dependencies=[Depends(verifier_cle)])
def registre_envois(copro: str = Copro, document: str | None = Query(None, max_length=80)) -> list[dict]:
    fiche_de(copro)
    return [e for e in papier.charger_registre(DOSSIER_DATA, copro) if not document or e["document"] == document]


@app.post("/copros/{copro}/envois", status_code=201, dependencies=[Depends(verifier_cle)])
def nouvel_envoi(corps: NouvelEnvoi, copro: str = Copro) -> dict:
    try:
        return papier.enregistrer_envoi(DOSSIER_DATA, copro, fiche_de(copro), corps.coproprietaire, corps.document,
                                        corps.canal, corps.envoye_le, corps.numero, corps.notifie_le, corps.note)
    except papier.PapierInvalide as e:
        raise HTTPException(422, str(e))


@app.put("/copros/{copro}/envois/{eid}", dependencies=[Depends(verifier_cle)])
def maj_envoi(corps: MajEnvoi, copro: str = Copro, eid: str = PathParam(..., pattern=r"^E\d{4}$")) -> dict:
    fiche_de(copro)
    try:
        return papier.mettre_a_jour_envoi(DOSSIER_DATA, copro, eid, corps.statut, corps.notifie_le, corps.numero,
                                          corps.note)
    except papier.PapierInvalide as e:
        raise HTTPException(404 if "inconnu" in str(e).lower() and "envoi" in str(e).lower() else 422, str(e))


@app.get("/copros/{copro}/ag/{ag_id}/agenda.ics", dependencies=[Depends(verifier_cle)])
def agenda_ag(copro: str = Copro, ag_id: str = AgId) -> Response:
    try:
        ics = rappel_ag.generer_ics(fiche_de(copro), ag_de(copro, ag_id), copro)
    except rappel_ag.RappelInvalide as e:
        raise HTTPException(422, str(e))
    return Response(ics, media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="ag_{ag_id}.ics"'})


@app.get("/copros/{copro}/ag/{ag_id}/rappels", dependencies=[Depends(verifier_cle)])
def rappels_ag(copro: str = Copro, ag_id: str = AgId, au: date | None = Query(None)) -> dict:
    try:
        r = rappel_ag.rappels(fiche_de(copro), ag_de(copro, ag_id), copro, au)
    except rappel_ag.RappelInvalide as e:
        raise HTTPException(422, str(e))
    return r or {"copro": copro, "ag": ag_id, "rappel": None, "envois": [], "courrier": []}


@app.get("/rappels-ag", dependencies=[Depends(verifier_cle)])
def rappels_du_jour(au: date | None = Query(None)) -> dict:
    """Pour le workflow quotidien : un élément par mail à envoyer, toutes copros et AG confondues.
    Une AG à l'heure illisible est signalée au lieu de bloquer les autres."""
    jour = au or date.today()
    envois, courriers, erreurs = [], [], []
    for c in lister_copros():
        fiche = fiche_de(c)
        for a in assemblee.lister_ag(DOSSIER_DATA, c):
            try:
                r = rappel_ag.rappels(fiche, ag_de(c, a["id"]), c, jour)
            except rappel_ag.RappelInvalide as e:
                erreurs.append({"copro": c, "ag": a["id"], "erreur": str(e)})
                continue
            if not r:
                continue
            envois += [{**e, "copro": c, "ag": a["id"], "rappel": r["rappel"], "fichier_ics": r["fichier_ics"]}
                       for e in r["envois"]]
            if r["courrier"]:
                syndic = next(x for x in fiche["coproprietaires"]
                              if x["id"] == fiche["gouvernance"]["syndic"]["coproprietaire_id"])
                courriers.append({"copro": c, "copropriete": r["copropriete"], "ag": a["id"], "rappel": r["rappel"],
                                  "syndic_email": syndic.get("email"), "noms": [x["nom"] for x in r["courrier"]],
                                  "note": r["note_courrier"]})
    return {"au": jour.isoformat(), "nb_envois": len(envois), "envois": envois, "courriers": courriers,
            "erreurs": erreurs}


@app.get("/copros/{copro}/ag/{ag_id}/convocations", dependencies=[Depends(verifier_cle)])
def controle_convocations(copro: str = Copro, ag_id: str = AgId) -> dict:
    fiche, a = fiche_de(copro), ag_de(copro, ag_id)
    return papier.controle_convocations(fiche, a, papier.charger_registre(DOSSIER_DATA, copro))


# --------------------------------------------------------------------------- #
# Votes
# --------------------------------------------------------------------------- #
class OuvertureSondage(BaseModel):
    options: list[str] | None = Field(None, description="Devis soumis à l'avis (défaut : tous les devis non expirés)")
    duree_jours: int = Field(7, ge=1, le=30, description="Durée du sondage")


ID_SONDAGE = r"^S\d{1,3}$"
JETON = r"^[A-Za-z0-9_-]{20,40}$"


def _sondage_de(d: dict, sid: str) -> dict:
    s = next((x for x in d.get("sondages", []) if x["id"] == sid), None)
    if not s:
        raise HTTPException(404, f"Aucun sondage {sid} dans ce dossier")
    return s


@app.post("/copros/{copro}/travaux/{dossier_id}/sondages", status_code=201, dependencies=[Depends(verifier_cle)])
def ouvrir_sondage(corps: OuvertureSondage, copro: str = Copro, dossier_id: str = Dossier) -> dict:
    chemin, d = dossier_de(copro, dossier_id)
    fiche = fiche_de(copro)
    options = corps.options or [x["id"] for x in travaux.comparatif(fiche, d)["devis"] if not x["expire"]]
    try:
        sondage, jetons = vote.ouvrir_sondage(fiche, d, options, corps.duree_jours)
    except ValueError as e:
        raise HTTPException(422, str(e))
    d.setdefault("sondages", []).append(sondage)
    travaux.sauver_dossier(chemin, d)
    copros = {c["id"]: c for c in fiche["coproprietaires"]}
    return {"sondage": sondage["id"], "clos_le": sondage["clos_le"], "options": options,
            "invitations": [{"coproprietaire": cid, "nom": copros[cid]["nom"], "email": copros[cid].get("email"),
                             "envoi": papier.canal(fiche, cid)["canal"],
                             "lien": f"{URL_PUBLIQUE}/vote/{copro}/{dossier_id}/{sondage['id']}/{j}",
                             **({"bulletin_papier": f"/copros/{copro}/travaux/{dossier_id}/sondages/{sondage['id']}"
                                                    f"/bulletins/{cid}"}
                                if papier.canal(fiche, cid)["canal"] == "courrier" else {})}
                            for cid, j in jetons.items()],
            "avertissement": "Les liens ne sont affichés qu'une fois : ils ne sont pas conservés en clair."}


@app.get("/copros/{copro}/travaux/{dossier_id}/sondages/{sid}", dependencies=[Depends(verifier_cle)])
def resultats_sondage(copro: str = Copro, dossier_id: str = Dossier, sid: str = PathParam(..., pattern=ID_SONDAGE)) -> dict:
    _, d = dossier_de(copro, dossier_id)
    return vote.resultats_sondage(_sondage_de(d, sid))


@app.post("/copros/{copro}/travaux/{dossier_id}/sondages/{sid}/cloture", dependencies=[Depends(verifier_cle)])
def cloturer_sondage(copro: str = Copro, dossier_id: str = Dossier, sid: str = PathParam(..., pattern=ID_SONDAGE)) -> dict:
    chemin, d = dossier_de(copro, dossier_id)
    s = _sondage_de(d, sid)
    s["cloture_anticipee"] = datetime.now().replace(microsecond=0).isoformat()
    travaux.sauver_dossier(chemin, d)
    return vote.resultats_sondage(s)


class Resolution(BaseModel):
    devis: str = Field(..., pattern=ID_DEVIS)
    bulletins: dict[str, str] = Field(..., description="{copropriétaire: pour | contre | abstention} ; absents omis")
    second_vote_24: dict[str, str] | None = Field(None, description="Second vote (art. 25-1), si l'AG y a procédé")


class Depouillement(BaseModel):
    majorite: str = Field("24", pattern=r"^(24|25|26)$")
    resolutions: list[Resolution] = Field(..., min_length=1, description="Dans l'ordre de l'ordre du jour")


@app.post("/copros/{copro}/travaux/{dossier_id}/ag", dependencies=[Depends(verifier_cle)])
def depouiller_ag(corps: Depouillement, copro: str = Copro, dossier_id: str = Dossier) -> dict:
    chemin, d = dossier_de(copro, dossier_id)
    voix = vote.electorat(fiche_de(copro), d["cle"])
    try:
        res = vote.depouiller_ag([r.model_dump() for r in corps.resolutions], voix, corps.majorite)
    except ValueError as e:
        raise HTTPException(422, str(e))
    d["ag"] = res
    travaux.sauver_dossier(chemin, d)
    return res


class VoteConseil(BaseModel):
    resolutions: list[Resolution] = Field(..., min_length=1)


@app.post("/copros/{copro}/travaux/{dossier_id}/conseil", dependencies=[Depends(verifier_cle)])
def voter_conseil(corps: VoteConseil, copro: str = Copro, dossier_id: str = Dossier) -> dict:
    chemin, d = dossier_de(copro, dossier_id)
    fiche = fiche_de(copro)
    membres = fiche["gouvernance"].get("conseil_syndical", [])
    aig = travaux.aiguillage(fiche, d, travaux.comparatif(fiche, d)["reference_ttc"])
    res, retenu = [], None
    try:
        for r in corps.resolutions:
            if retenu:
                res.append({"devis": r.devis, "statut": "sans_objet"})
                continue
            v = vote.vote_conseil(r.bulletins, membres)
            v["devis"], v["statut"] = r.devis, "adoptee" if v["adoptee"] else "rejetee"
            retenu = r.devis if v["adoptee"] else None
            res.append(v)
    except ValueError as e:
        raise HTTPException(422, str(e))
    sortie = {"devis_retenu": retenu, "resolutions": res,
              "avertissement": None if aig["circuit"] == "conseil_syndical" else
              "Attention : selon l'aiguillage, ce dossier ne relève pas d'une décision du conseil syndical "
              f"({aig['titre']}). Ce vote ne vaut qu'avis."}
    d["conseil"] = sortie
    travaux.sauver_dossier(chemin, d)
    return sortie


# --- Pages publiques : l'accès se fait par le jeton personnel, sans clé d'API -------------------- #
def _electeur(copro: str, dossier_id: str, sid: str, jeton: str):
    try:
        chemin, d = dossier_de(copro, dossier_id)
        s = _sondage_de(d, sid)
    except HTTPException:
        return None
    cid = vote.trouver_electeur(s, jeton)
    return (chemin, d, s, cid) if cid else None


def _page(copro, dossier_id, sid, jeton, message=None) -> HTMLResponse:
    trouve = _electeur(copro, dossier_id, sid, jeton)
    if not trouve:
        return HTMLResponse(page_vote.page_erreur("Ce lien de vote n'est pas valide. Vérifiez qu'il est complet, "
                                                  "ou demandez-en un nouveau au syndic."), status_code=404)
    _, d, s, cid = trouve
    fiche = fiche_de(copro)
    synth = travaux.synthese(fiche, d)
    nom = next(c["nom"] for c in fiche["coproprietaires"] if c["id"] == cid)
    html = page_vote.page_sondage(fiche["copropriete"]["nom"], d, s, cid, nom, synth["comparatif"],
                                  synth["resume_ia"], f"{URL_PUBLIQUE}/vote/{copro}/{dossier_id}/{sid}/{jeton}/comparatif.pdf",
                                  message, vote.est_ouvert(s))
    return HTMLResponse(html, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})


Jeton = PathParam(..., pattern=JETON)
Sid = PathParam(..., pattern=ID_SONDAGE)


# --------------------------------------------------------------------------- #
# Impayés : relevés bancaires, rapprochement, relances
# --------------------------------------------------------------------------- #
ID_OPERATION = r"^OP[0-9a-f]{10}$"
ID_RELANCE = r"^R\d{4}$"


@app.post("/copros/{copro}/banque/releves", dependencies=[Depends(verifier_cle)])
async def importer_releve(copro: str = Copro, fichier: UploadFile = File(..., description="Relevé CSV (5 Mo max)")) -> dict:
    fiche_de(copro)
    contenu = await fichier.read(banque.TAILLE_MAX + 1)
    try:
        r = banque.importer(DOSSIER_DATA, copro, contenu, fichier.filename or "releve.csv")
    except banque.ReleveInvalide as e:
        raise HTTPException(422, str(e))
    e = impayes.etat(fiche_de(copro), DOSSIER_SORTIE, DOSSIER_DATA, copro)
    return _json({**r, "rapprochement": e["rapprochement"], "a_confirmer": len(e["a_confirmer"])})


@app.get("/copros/{copro}/impayes", dependencies=[Depends(verifier_cle)])
def etat_impayes(copro: str = Copro, au: date | None = Query(None),
                 detail: bool = Query(False, description="true = inclure toutes les opérations et échéances")) -> dict:
    e = impayes.etat(fiche_de(copro), DOSSIER_SORTIE, DOSSIER_DATA, copro, au)
    if not detail:
        e.pop("operations")
        e["comptes"] = {cid: {k: v for k, v in c.items() if k not in ("echeances", "paiements")}
                        for cid, c in e["comptes"].items() if c["impaye"] or c["solde"]}
    return _json(e)


@app.get("/copros/{copro}/impayes.pdf", dependencies=[Depends(verifier_cle)])
def pdf_impayes(copro: str = Copro, au: date | None = Query(None)) -> FileResponse:
    fiche = fiche_de(copro)
    e = impayes.etat(fiche, DOSSIER_SORTIE, DOSSIER_DATA, copro, au)
    chemin = impayes.generer_etat(fiche, e, DOSSIER_SORTIE / copro / "recouvrement" / f"etat_impayes_{e['au']}.pdf")
    return FileResponse(chemin, media_type="application/pdf", filename=chemin.name)


class Affectation(BaseModel):
    statut: Literal["confirme", "ignore", "annule"]
    coproprietaire: str | None = Field(None, pattern=ID_COPRO)


@app.put("/copros/{copro}/banque/operations/{op_id}", dependencies=[Depends(verifier_cle)])
def affecter_operation(corps: Affectation, copro: str = Copro, op_id: str = PathParam(..., pattern=ID_OPERATION)) -> dict:
    try:
        return impayes.affecter(fiche_de(copro), DOSSIER_DATA, copro, op_id, corps.statut, corps.coproprietaire)
    except impayes.RecouvrementInvalide as e:
        raise HTTPException(422, str(e))


class Ajustement(BaseModel):
    coproprietaire: str = Field(..., pattern=ID_COPRO)
    le: date = Field(..., description="Date d'exigibilité (ou de l'avoir)")
    libelle: str = Field(..., min_length=3, max_length=120)
    montant: Decimal = Field(..., max_digits=12, decimal_places=2)
    nature: Literal["solde_anterieur", "travaux", "frais_recouvrement", "avoir", "autre"] = "autre"


@app.post("/copros/{copro}/impayes/ajustements", dependencies=[Depends(verifier_cle)])
def ajouter_ajustement(corps: Ajustement, copro: str = Copro) -> dict:
    try:
        return impayes.ajouter_ajustement(fiche_de(copro), DOSSIER_DATA, copro, corps.coproprietaire, corps.le,
                                          corps.libelle, corps.montant, corps.nature)
    except impayes.RecouvrementInvalide as e:
        raise HTTPException(422, str(e))


@app.post("/copros/{copro}/relances/{cid}", dependencies=[Depends(verifier_cle)])
def preparer_relance(copro: str = Copro, cid: str = PathParam(..., pattern=ID_COPRO), au: date | None = Query(None)) -> dict:
    """Prépare la relance que Mitoyen propose pour ce copropriétaire (jamais une étape sautée)."""
    try:
        r = impayes.preparer_relance(fiche_de(copro), DOSSIER_SORTIE, DOSSIER_DATA, copro, cid,
                                     DOSSIER_SORTIE / copro / "recouvrement", au)
    except impayes.RecouvrementInvalide as e:
        raise HTTPException(409, str(e))
    r.pop("chemin")
    return _json({**r, "telechargement": f"/copros/{copro}/relances/{r['id']}.pdf"})


@app.get("/copros/{copro}/relances/{rid}.pdf", dependencies=[Depends(verifier_cle)])
def pdf_relance(copro: str = Copro, rid: str = PathParam(..., pattern=ID_RELANCE)) -> FileResponse:
    rel = next((x for x in impayes.charger_relances(DOSSIER_DATA, copro) if x["id"] == rid), None)
    chemin = DOSSIER_SORTIE / copro / "recouvrement" / rel["fichier"] if rel else None
    if not chemin or not chemin.is_file():
        raise HTTPException(404, "Relance introuvable")
    return FileResponse(chemin, media_type="application/pdf", filename=chemin.name)


class SuiviRelance(BaseModel):
    statut: Literal["envoyee", "annulee"]
    envoyee_le: date | None = None
    moyen: Literal["email", "courrier", "remise_main", "lrar", "lre", "commissaire_justice"] | None = None
    presentee_le: date | None = Field(None, description="Première présentation du recommandé (avis de réception)")


@app.put("/copros/{copro}/relances/{rid}", dependencies=[Depends(verifier_cle)])
def suivre_relance(corps: SuiviRelance, copro: str = Copro, rid: str = PathParam(..., pattern=ID_RELANCE)) -> dict:
    try:
        return impayes.marquer(fiche_de(copro), DOSSIER_DATA, copro, rid, corps.statut, corps.envoyee_le, corps.moyen,
                               corps.presentee_le)
    except impayes.RecouvrementInvalide as e:
        raise HTTPException(422, str(e))


# --------------------------------------------------------------------------- #
# Meublés de tourisme (loi Le Meur)
# --------------------------------------------------------------------------- #
ID_DECLARATION_MT = r"^MT\d{3}$"


class DeclarationMT(BaseModel):
    lot: int = Field(..., ge=1)
    recue_le: date
    informe_par: Literal["proprietaire", "locataire"] = "proprietaire"
    residence_principale: bool | None = Field(None, description="Le logement est-il la résidence principale du loueur ?")
    numero_enregistrement: str | None = Field(None, max_length=40, description="Numéro de déclaration en mairie")
    debut: date | None = None


@app.get("/copros/{copro}/meubles-tourisme", dependencies=[Depends(verifier_cle)])
def meubles_tourisme_etat(copro: str = Copro, au: date | None = Query(None)) -> dict:
    fiche = fiche_de(copro)
    reg = meubles_tourisme.charger(DOSSIER_DATA, copro)
    jour = au or date.today()
    return {"declarations": reg, "actives": len(meubles_tourisme.actives(reg, jour)),
            "a_presenter_en_ag": [d["id"] for d in reg if not d.get("inscrite_ag")],
            "interdiction": meubles_tourisme.eligibilite(fiche)}


@app.post("/copros/{copro}/meubles-tourisme/declarations", status_code=201, dependencies=[Depends(verifier_cle)])
def meubles_tourisme_declarer(corps: DeclarationMT, copro: str = Copro) -> dict:
    try:
        d = meubles_tourisme.enregistrer(fiche_de(copro), DOSSIER_DATA, copro, corps.lot, corps.recue_le,
                                         corps.informe_par, corps.residence_principale, corps.numero_enregistrement,
                                         corps.debut)
    except meubles_tourisme.DeclarationInvalide as e:
        raise HTTPException(422, str(e))
    return {**d, "a_faire": ["Le point d'information sera ajouté automatiquement à la prochaine AG que vous créerez.",
                             f"Afficher l'information dans le hall : /copros/{copro}/meubles-tourisme/affichage.pdf"]}


class FinMT(BaseModel):
    fin_le: date


@app.put("/copros/{copro}/meubles-tourisme/declarations/{did}", dependencies=[Depends(verifier_cle)])
def meubles_tourisme_fin(corps: FinMT, copro: str = Copro, did: str = PathParam(..., pattern=ID_DECLARATION_MT)) -> dict:
    try:
        return meubles_tourisme.terminer(DOSSIER_DATA, copro, did, corps.fin_le)
    except meubles_tourisme.DeclarationInvalide as e:
        raise HTTPException(422, str(e))


@app.get("/copros/{copro}/meubles-tourisme/affichage.pdf", dependencies=[Depends(verifier_cle)])
def meubles_tourisme_affichage(copro: str = Copro, au: date | None = Query(None)) -> FileResponse:
    fiche = fiche_de(copro)
    jour = au or date.today()
    futures = [a for a in assemblee.lister_ag(DOSSIER_DATA, copro) if a["date"] >= jour.isoformat() and not a["depouillee"]]
    chemin = meubles_tourisme.generer_affichage(
        fiche, meubles_tourisme.charger(DOSSIER_DATA, copro),
        DOSSIER_SORTIE / copro / "affichage" / f"meubles_tourisme_{jour:%Y%m%d}.pdf", jour,
        date.fromisoformat(futures[0]["date"]) if futures else None)
    return FileResponse(chemin, media_type="application/pdf", filename=chemin.name)


@app.get("/copros/{copro}/meubles-tourisme/resolution", dependencies=[Depends(verifier_cle)])
def meubles_tourisme_resolution(copro: str = Copro) -> dict:
    """Projet de résolution, à utiliser si un copropriétaire demande l'inscription de la question."""
    try:
        return meubles_tourisme.projet_resolution(fiche_de(copro))
    except meubles_tourisme.DeclarationInvalide as e:
        raise HTTPException(409, str(e))


# --------------------------------------------------------------------------- #
# Pack nouvel arrivant
# --------------------------------------------------------------------------- #
Lots = Query(..., min_length=1, max_length=20, description="Numéros des lots (répéter le paramètre)")


@app.get("/copros/{copro}/bienvenue/proprietaire.pdf", dependencies=[Depends(verifier_cle)])
def bienvenue_proprietaire(copro: str = Copro, lots: list[int] = Lots,
                           nom: str = Query(..., min_length=2, max_length=80),
                           grand: bool = Query(False, description="Grands caractères"),
                           au: date | None = Query(None)) -> FileResponse:
    jour = au or date.today()
    chemin = DOSSIER_SORTIE / copro / "bienvenue" / f"bienvenue_{jour:%Y%m%d}_lots_{'-'.join(map(str, sorted(lots)))}.pdf"
    try:
        nouvel_arrivant.pack_proprietaire(fiche_de(copro), lots, nom, chemin, DOSSIER_DATA, copro, jour, grand)
    except nouvel_arrivant.PackInvalide as e:
        raise HTTPException(422, str(e))
    return FileResponse(chemin, media_type="application/pdf", filename=chemin.name)


@app.get("/copros/{copro}/bienvenue/locataire.pdf", dependencies=[Depends(verifier_cle)])
def bienvenue_locataire(copro: str = Copro, lots: list[int] = Lots,
                        grand: bool = Query(False, description="Grands caractères")) -> FileResponse:
    chemin = DOSSIER_SORTIE / copro / "bienvenue" / f"locataire_lots_{'-'.join(map(str, sorted(lots)))}.pdf"
    try:
        nouvel_arrivant.pack_locataire(fiche_de(copro), lots, chemin, DOSSIER_DATA, copro, grand=grand)
    except nouvel_arrivant.PackInvalide as e:
        raise HTTPException(422, str(e))
    return FileResponse(chemin, media_type="application/pdf", filename=chemin.name)


# --------------------------------------------------------------------------- #
# Dossier de vente (art. L. 721-2 du CCH)
# --------------------------------------------------------------------------- #
ID_VENTE = r"^\d{8}-lots(-\d{1,4}){1,20}$"


@app.get("/copros/{copro}/fiche-synthetique", dependencies=[Depends(verifier_cle)])
def fiche_synthetique(copro: str = Copro, au: date | None = Query(None)) -> dict:
    return vente.fiche_synthetique(fiche_de(copro), au)


@app.get("/copros/{copro}/fiche-synthetique.pdf", dependencies=[Depends(verifier_cle)])
def pdf_fiche_synthetique(copro: str = Copro, au: date | None = Query(None)) -> FileResponse:
    jour = au or date.today()
    sortie = DOSSIER_SORTIE / copro / "vente"
    sortie.mkdir(parents=True, exist_ok=True)
    chemin = vente.generer_fiche_synthetique(fiche_de(copro), sortie / f"fiche_synthetique_{jour:%Y%m%d}.pdf", jour)
    return FileResponse(chemin, media_type="application/pdf", filename=chemin.name)


class ChargesExercice(BaseModel):
    exercice: int = Field(..., ge=2000, le=2100)
    budget: Decimal = Field(Decimal("0"), ge=0, max_digits=12, decimal_places=2)
    hors_budget: Decimal = Field(Decimal("0"), ge=0, max_digits=12, decimal_places=2)


class DemandeVente(BaseModel):
    lots: list[int] = Field(..., min_length=1, max_length=20)
    charges_payees: list[ChargesExercice] = Field(default_factory=list, max_length=2)
    impayes_vendeur: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    acquereur_coproprietaire: bool = False
    au: date | None = None


def comptes_vendeur_complets(fiche: dict, copro: str, lots: list[int], jour: date, fournis: dict | None = None) -> dict:
    """Les comptes du vendeur tirés de la comptabilité tenue dans Mitoyen ; ce que le syndic
    fournit lui-même l'emporte (exercice par exercice pour les charges payées)."""
    try:
        E, st, bud = etat_date.journal_et_budgets(fiche, DOSSIER_SORTIE, DOSSIER_DATA, copro)
        auto = etat_date.comptes_vendeur(fiche, E, st, bud, lots, jour)
    except etat_date.EtatDateInvalide as e:
        raise vente.VenteInvalide(str(e)) from e
    fournis = fournis or {}
    par_ex = {int(c["exercice"]): c for c in auto.get("charges_payees", [])}
    par_ex.update({int(c["exercice"]): c for c in fournis.get("charges_payees") or []})
    res = {**auto, "charges_payees": [par_ex[k] for k in sorted(par_ex)][-2:]}
    if fournis.get("impayes_vendeur") is not None:
        res["impayes_vendeur"] = fournis["impayes_vendeur"]
    return res


@app.post("/copros/{copro}/ventes", dependencies=[Depends(verifier_cle)])
def creer_dossier_vente(corps: DemandeVente, copro: str = Copro) -> dict:
    """Les comptes du vendeur (charges payées, impayés) viennent de la comptabilité
    du syndic ; sans eux, le dossier est produit et les rubriques sont marquées
    « à compléter »."""
    fiche = fiche_de(copro)
    fournis = {"charges_payees": [c.model_dump() for c in corps.charges_payees],
               "impayes_vendeur": corps.impayes_vendeur}
    try:
        comptes = comptes_vendeur_complets(fiche, copro, corps.lots, corps.au or date.today(), fournis)
        r = vente.generer_dossier(fiche, corps.lots, DOSSIER_SORTIE / copro / "ventes", DOSSIER_DATA,
                                  copro, comptes, corps.acquereur_coproprietaire, corps.au)
    except vente.VenteInvalide as e:
        raise HTTPException(422, str(e))
    r.pop("chemin_archive")
    return _json({**r, "telechargement": f"/copros/{copro}/ventes/{r['id']}.zip"})


@app.get("/copros/{copro}/ventes/{vente_id}.zip", dependencies=[Depends(verifier_cle)])
def zip_dossier_vente(copro: str = Copro, vente_id: str = PathParam(..., pattern=ID_VENTE)) -> FileResponse:
    chemin = DOSSIER_SORTIE / copro / "ventes" / vente_id / f"dossier_vente_{vente_id}.zip"
    if not chemin.is_file():
        raise HTTPException(404, "Dossier de vente introuvable")
    return FileResponse(chemin, media_type="application/zip", filename=chemin.name)


def preparer_transmission(copro: str, formulaire: dict, jour: date | None = None) -> dict:
    """Dossier de transfert vers un autre syndic : bordereau, état des comptes, tableaux CSV, archives."""
    jour = jour or date.today()
    fiche = fiche_de(copro)
    p = transmission.parametres(formulaire)
    e = impayes.etat(fiche, DOSSIER_SORTIE, DOSSIER_DATA, copro, jour)
    return transmission.generer(fiche, p, e, impayes.charger_relances(DOSSIER_DATA, copro), DOSSIER_DATA,
                                DOSSIER_SORTIE, copro, DOSSIER_SORTIE / copro / "transmission" / f"{jour:%Y%m%d}", jour)


class CorpsTransmission(BaseModel):
    successeur: str = Field(..., min_length=1, max_length=120)
    successeur_adresse: str = Field("", max_length=300)
    cessation: date
    date_soldes: date | None = None
    solde_courant: Decimal | None = None
    solde_fonds_travaux: Decimal | None = None


@app.post("/copros/{copro}/transmission", dependencies=[Depends(verifier_cle)])
def creer_transmission(corps: CorpsTransmission, copro: str = Copro) -> FileResponse:
    form = {k: ("" if v is None else str(v)) for k, v in corps.model_dump().items()}
    try:
        r = preparer_transmission(copro, form)
    except transmission.TransmissionInvalide as ex:
        raise HTTPException(422, str(ex))
    return FileResponse(r["chemin"], media_type="application/zip", filename=r["archive"])


# --------------------------------------------------------------------------- #
# Signalements des copropriétaires (lien secret de la copropriété, sans clé d'API)
# --------------------------------------------------------------------------- #
MAX_SIGNALEMENTS_PAR_JOUR = 30


def lien_signalement(copro: str) -> str:
    return f"{URL_PUBLIQUE}/signaler/{copro}/{signalements.jeton(DOSSIER_DATA, copro)}"


def _page_signaler(copro: str, message: str | None = None, erreur: str | None = None, saisie: dict | None = None,
                   statut: int = 200) -> HTMLResponse:
    fiche = fiche_de(copro)
    donnees = signalements.charger(DOSSIER_DATA, copro)
    html = page_signalement.page_signaler(
        fiche["copropriete"]["nom"], signalements.CATEGORIES, signalements.NIVEAUX,
        signalements.URGENCES + signalements.astreintes(fiche), signalements.vue_publique(donnees),
        message, erreur, saisie)
    return HTMLResponse(html, status_code=statut, headers={"Cache-Control": "no-store"})


def lien_bulletin(copro: str) -> str | None:
    r = bulletin.reglages(DOSSIER_DATA, copro)
    return f"{URL_PUBLIQUE}/bulletin/{copro}/{r['jeton']}" if r.get("actif") and r.get("jeton") else None


@app.get("/bulletin/{copro}/{jeton}", response_class=HTMLResponse, include_in_schema=False)
def page_bulletin_public(request: Request, copro: str = Copro, jeton: str = Jeton):
    """Le bulletin de santé, partagé par le syndic : aucune donnée personnelle."""
    from . import interface
    if copro not in lister_copros() or not bulletin.jeton_valide(DOSSIER_DATA, copro, jeton):
        return HTMLResponse(page_signalement._page(
            "Lien invalide", "", "<h1>Lien invalide</h1><p class=\"erreur\">Ce bulletin n’est plus partagé, ou son "
            "lien a été renouvelé. Demandez le lien à jour au vendeur ou au syndic.</p>"), status_code=404)
    b = bulletin.depuis_mitoyen(fiche_de(copro), DOSSIER_SORTIE, DOSSIER_DATA, copro, date.today())
    return interface.templates.TemplateResponse(request, "bulletin_public.html", {"b": b},
                                                headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex"})


def lien_consultation(copro: str, cid: str, jeton: str) -> str:
    return f"{URL_PUBLIQUE}/consulter/{copro}/{cid}/{jeton}"


def _page_consultation(copro: str, cid: str, jeton: str, message: str | None = None, statut: int = 200):
    try:
        c = consultation.charger(DOSSIER_DATA, copro, cid)
    except consultation.ConsultationInvalide:
        c = None
    e = consultation.trouver(c, jeton) if c else None
    if not e:
        return HTMLResponse(page_vote.page_erreur("Ce lien n'est pas valide. Vérifiez qu'il est complet, ou "
                                                  "demandez-en un nouveau au syndic."), status_code=404)
    fiche = fiche_de(copro)
    nom = next(x["nom"] for x in fiche["coproprietaires"] if x["id"] == e)
    v = c["electeurs"][e]
    html = page_vote.page_consultation(fiche["copropriete"]["nom"], c, nom, v["choix"], v["le"], c["repondre_avant"],
                                       consultation.ouverte(c), message)
    return HTMLResponse(html, status_code=statut, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})


@app.get("/consulter/{copro}/{cid}/{jeton}", response_class=HTMLResponse, include_in_schema=False)
def page_consulter(copro: str = Copro, cid: str = PathParam(..., pattern=r"^C\d{3}$"), jeton: str = Jeton):
    return _page_consultation(copro, cid, jeton)


@app.post("/consulter/{copro}/{cid}/{jeton}", response_class=HTMLResponse, include_in_schema=False)
def voter_consultation(copro: str = Copro, cid: str = PathParam(..., pattern=r"^C\d{3}$"), jeton: str = Jeton,
                       choix: str = Form(..., max_length=20)):
    try:
        c = consultation.charger(DOSSIER_DATA, copro, cid)
    except consultation.ConsultationInvalide:
        return _page_consultation(copro, cid, jeton)
    e = consultation.trouver(c, jeton)
    if not e:
        return _page_consultation(copro, cid, jeton)
    try:
        consultation.voter(c, e, choix, "lien")
    except consultation.ConsultationInvalide as err:
        return HTMLResponse(page_vote.page_erreur(str(err)), status_code=409)
    consultation.sauver(DOSSIER_DATA, copro, c)
    return _page_consultation(copro, cid, jeton, "Merci, votre vote est enregistré.")


@app.get("/signaler/{copro}/{jeton}", response_class=HTMLResponse, include_in_schema=False)
def page_signaler(copro: str = Copro, jeton: str = Jeton, envoye: int = 0):
    if copro not in lister_copros() or not signalements.jeton_valide(DOSSIER_DATA, copro, jeton):
        return HTMLResponse(page_signalement.page_lien_invalide(), status_code=404)
    return _page_signaler(copro, "Merci, votre signalement est arrivé chez le syndic." if envoye else None)


@app.post("/signaler/{copro}/{jeton}", response_class=HTMLResponse, include_in_schema=False)
async def envoyer_signalement(copro: str = Copro, jeton: str = Jeton,
                              categorie: str = Form("", max_length=20), niveau: str = Form("genant", max_length=10),
                              lieu: str = Form("", max_length=400), description: str = Form("", max_length=6000),
                              contact: str = Form("", max_length=400), site_web: str = Form("", max_length=200),
                              photo: UploadFile | None = File(None)):
    if copro not in lister_copros() or not signalements.jeton_valide(DOSSIER_DATA, copro, jeton):
        return HTMLResponse(page_signalement.page_lien_invalide(), status_code=404)
    saisie = {"categorie": categorie, "niveau": niveau, "lieu": lieu, "description": description, "contact": contact}
    if site_web:                                        # champ piège : rempli seulement par les robots
        return Response(status_code=303, headers={"Location": f"/signaler/{copro}/{jeton}?envoye=1"})
    aujourdhui_iso = date.today().isoformat()
    du_jour = sum(1 for x in signalements.charger(DOSSIER_DATA, copro)["signalements"]
                  if x["cree_le"].startswith(aujourdhui_iso))
    if du_jour >= MAX_SIGNALEMENTS_PAR_JOUR:
        return _page_signaler(copro, erreur="Trop de signalements aujourd’hui : réessayez demain ou prévenez le syndic "
                                            "par sa boîte aux lettres.", saisie=saisie, statut=429)
    contenu = None
    if photo is not None and photo.filename:
        contenu = await photo.read(signalements.TAILLE_MAX_PHOTO + 1)
    try:
        signalements.creer(DOSSIER_DATA, copro, categorie, lieu, description, niveau, contact, contenu or None)
    except signalements.SignalementInvalide as e:
        return _page_signaler(copro, erreur=str(e), saisie=saisie, statut=422)
    return Response(status_code=303, headers={"Location": f"/signaler/{copro}/{jeton}?envoye=1"})


@app.get("/vote/{copro}/{dossier_id}/{sid}/{jeton}", response_class=HTMLResponse, include_in_schema=False)
def page_de_vote(copro: str = Copro, dossier_id: str = Dossier, sid: str = Sid, jeton: str = Jeton):
    return _page(copro, dossier_id, sid, jeton)


@app.post("/vote/{copro}/{dossier_id}/{sid}/{jeton}", response_class=HTMLResponse, include_in_schema=False)
def enregistrer_vote(copro: str = Copro, dossier_id: str = Dossier, sid: str = Sid, jeton: str = Jeton,
                     choix: str = Form(..., max_length=20)):
    trouve = _electeur(copro, dossier_id, sid, jeton)
    if not trouve:
        return _page(copro, dossier_id, sid, jeton)
    chemin, d, s, cid = trouve
    try:
        vote.voter_sondage(s, cid, choix)
    except ValueError as e:
        return HTMLResponse(page_vote.page_erreur(str(e)), status_code=409)
    travaux.sauver_dossier(chemin, d)
    return _page(copro, dossier_id, sid, jeton, "Merci, votre avis est enregistré.")


@app.get("/vote/{copro}/{dossier_id}/{sid}/{jeton}/comparatif.pdf", include_in_schema=False)
def comparatif_electeur(copro: str = Copro, dossier_id: str = Dossier, sid: str = Sid, jeton: str = Jeton):
    trouve = _electeur(copro, dossier_id, sid, jeton)
    if not trouve:
        raise HTTPException(404, "Lien invalide")
    chemin, d, _, _ = trouve
    fiche = fiche_de(copro)
    sortie = travaux.generer_pdf(fiche, travaux.synthese(fiche, d), chemin / "comparatif.pdf")
    return FileResponse(sortie, media_type="application/pdf", filename=f"comparatif_{dossier_id}.pdf")

# --------------------------------------------------------------------------- #
# Règlement de copropriété en clair
# --------------------------------------------------------------------------- #
@app.post("/copros/{copro}/reglement", status_code=201, dependencies=[Depends(verifier_cle)])
async def importer_reglement(copro: str = Copro,
                             fichier: UploadFile = File(..., description="Le règlement en PDF (texte sélectionnable)")) -> dict:
    fiche_de(copro)
    try:
        r = reglement.importer(DOSSIER_DATA, copro, await fichier.read(reglement.TAILLE_MAX_PDF + 1),
                               fichier.filename or "reglement.pdf")
    except reglement.ReglementInvalide as e:
        raise HTTPException(422, str(e))
    return {"articles": len(r["articles"]), "source": r["source"]}


@app.post("/copros/{copro}/reglement/redaction", dependencies=[Depends(verifier_cle)])
def rediger_reglement(copro: str = Copro) -> dict:
    fiche_de(copro)
    r = reglement.charger(DOSSIER_DATA, copro)
    if not r:
        raise HTTPException(404, "Aucun règlement importé")
    try:
        r = reglement.rediger(DOSSIER_DATA, copro, r)
    except resume_ia.IAIndisponible as e:
        raise HTTPException(503, str(e))
    return {"themes": r["themes"], "points_a_verifier": r["points_a_verifier"]}


@app.get("/copros/{copro}/reglement", dependencies=[Depends(verifier_cle)])
def voir_reglement(copro: str = Copro) -> dict:
    fiche_de(copro)
    r = reglement.charger(DOSSIER_DATA, copro)
    if not r:
        raise HTTPException(404, "Aucun règlement importé")
    return {**{k: r[k] for k in ("source", "importe_le", "themes", "redaction", "points_a_verifier", "valide_le")},
            "articles": len(r["articles"])}


@app.get("/copros/{copro}/reglement-en-clair.pdf", dependencies=[Depends(verifier_cle)])
def pdf_reglement(copro: str = Copro, usage: bool = Query(False, description="Seulement ce qui concerne l'occupant")) -> FileResponse:
    fiche = fiche_de(copro)
    r = reglement.charger(DOSSIER_DATA, copro)
    if not r or not r.get("themes"):
        raise HTTPException(404, "Pas encore de version en clair")
    sortie = DOSSIER_SORTIE / copro / "reglement"
    chemin = reglement.generer_pdf(fiche, r, sortie / ("reglement_en_clair_usage.pdf" if usage else "reglement_en_clair.pdf"),
                                   reglement.USAGE_LOCATAIRE if usage else None)
    return FileResponse(chemin, media_type="application/pdf", filename=chemin.name)



# --------------------------------------------------------------------------- #
# Interface web du syndic (/app), branchée en dernier : elle s'appuie sur ce module
# --------------------------------------------------------------------------- #
from . import interface  # noqa: E402

app.mount("/statique", interface.statiques, name="statique")
app.include_router(interface.routeur)

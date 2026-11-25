# Installation

[← Retour à l'accueil](../README.md)

## Avec Docker (recommandé)

```bash
cp .env.example .env
# remplir MOTEUR_TOKEN et N8N_ENCRYPTION_KEY :
python -c "import secrets; print(secrets.token_urlsafe(32))"

mkdir -p out          # sous Linux : sudo chown 1000 out
docker compose up -d --build
```

- Documentation interactive du moteur : http://localhost:8000/docs (bouton *Authorize* → ta clé)
- n8n : http://localhost:5678

Pour le résumé IA des devis, ajouter `MISTRAL_API_KEY` dans `.env`. Pour que les liens de vote fonctionnent hors de ta machine, renseigner `MOTEUR_URL_PUBLIQUE` (adresse HTTPS du moteur).

## Brancher les workflows dans n8n

1. **Import** : Workflows → *Import from File* → un fichier du dossier `workflows/`
2. **Identifiant « Moteur syndic »** : type *Header Auth*, nom `X-API-Key`, valeur = ton `MOTEUR_TOKEN`
3. **Identifiant « SMTP copro »** : ton serveur d'envoi de mails
4. **Nœud Config** : ton adresse dans `email_syndic`, et garde `mode_test = true` pour commencer

En mode test, **tous les mails arrivent chez le syndic**, préfixés `[TEST]`. Aucun copropriétaire ne reçoit rien.

| Workflow | Déclenchement | Ce qu'il fait |
|---|---|---|
| `appel_de_fonds.json` | Manuel, chaque trimestre | Génère les avis, attend la validation du syndic, puis les envoie |
| `rappel_ag.json` | Chaque jour à 9h | Rappels d'AG à J-7 et la veille, puis les résultats le lendemain du dépouillement, avec « L'AG en bref » et les fichiers d'agenda |
| `echeancier_hebdo.json` | Chaque lundi à 8h | Envoie à chaque syndic ses échéances : contrats à résilier, diagnostics, AG, plan de travaux, fin de mandat |

<p align="center"><img src="apercu_echeancier.png" alt="Aperçu du mail d'échéancier" width="560"></p>

## Sans Docker (développement)

```bash
pip install -r moteur/requirements.txt
python core/fiche_copro.py config/mimosas.yaml --date 2027-02-15     # contrôle de la fiche + échéances
python core/avis_appel.py config/mimosas.yaml --trimestre 1          # avis d'appel de fonds en PROJET
python core/plan_travaux.py config/mimosas.yaml --pdf plan.pdf       # projection du plan de travaux
MOTEUR_TOKEN=dev uvicorn moteur.api:app --reload                     # l'API et l'interface (/app)
python -m pytest tests/                                              # les tests
```

## Démonstration de l'interface

```bash
python scripts/demo_interface.py
MOTEUR_DATA_DIR=demo/data MOTEUR_OUT_DIR=demo/out INTERFACE_MOT_DE_PASSE=demo uvicorn moteur.api:app --reload
```

Puis ouvrir http://localhost:8000/app/mimosas?au=2027-05-20 (mot de passe : `demo`). Voir [interface.md](interface.md).

## Démonstration travaux et devis

Avec le moteur lancé, `bash scripts/demo_travaux.sh` crée un dossier sur la copro fictive, dépose les 3 devis d'exemple de `exemples/devis/`, vérifie les entreprises, demande le résumé à Mistral puis télécharge le comparatif PDF.

## Ta propre copropriété

Copier `config/mimosas.yaml` sous un autre nom (par exemple `config/ma-copro.yaml`) et le remplir : lots, tantièmes, copropriétaires, budget, contrats. Ces fichiers sont exclus du dépôt par le `.gitignore` : seule la fiche fictive des Mimosas est publiée.

<p align="center">
  <img src="docs/logo.svg" alt="Logo Mitoyen" width="260">
</p>

# Mitoyen

> **Partagez les murs, plus les frais de syndic.**

Un assistant open source pour les syndics **bénévoles et coopératifs** de copropriétés de moins de 50 lots : appels de fonds, travaux, votes, plan de travaux, assemblée générale, dossier de vente, impayés. De quoi gérer son immeuble entre copropriétaires, sans payer un syndic professionnel.

**Principe : l'agent prépare, le syndic valide et signe.** Mitoyen assiste un syndic humain, il ne le remplace jamais.

<p align="center"><img src="docs/apercu_interface.png" alt="Le tableau de bord du syndic : ce qui est à faire, du plus urgent au moins pressé" width="820"></p>

> ⚠️ Projet en phase 1 (open source / portfolio). Toutes les données du dépôt sont **fictives** : la « Résidence Les Mimosas » et ses 24 lots n'existent pas.

## Ce que fait Mitoyen

| Brique | En bref | Détails |
|---|---|---|
| **Interface du syndic** | Un tableau de bord qui dit ce qui est à faire, du plus urgent au moins pressé ; paiements confirmés et relances préparées en un clic ; devis comparés sans parti pris ; plan de travaux simulé ; copropriétaires présentés comme sur le tableau d'interphone du hall | [Interface](docs/interface.md) |
| **Fiche et échéancier** | Une fiche par copro (lots, tantièmes, contrats, budget), contrôlée à chaque usage. Chaque lundi, le syndic reçoit ses échéances : contrats à résilier, diagnostics, AG, travaux à préparer | [Installation](docs/installation.md) |
| **Appels de fonds** | Un avis PDF par copropriétaire, réparti au centime près, validé par le syndic avant envoi | [Installation](docs/installation.md) |
| **Travaux et devis** | Comparatif des devis, quote-part de chacun, entreprises vérifiées dans les registres publics, résumé neutre rédigé par Mistral | [Travaux et vote](docs/travaux-et-vote.md) |
| **Vote** | Sondage consultatif en ligne ou sur papier, vote du conseil syndical, dépouillement selon les majorités de la loi de 1965 | [Travaux et vote](docs/travaux-et-vote.md) |
| **Plan de travaux vivant** | Projection du fonds de travaux sur 10 ans, minimum légal, cotisation lissée, ce que chacun paiera et quand | [Plan de travaux](docs/plan-de-travaux.md) |
| **Assemblée générale** | Calendrier légal, formulaires de vote par correspondance, rappels avec ajout à l'agenda, mandats, feuille de présence, brouillon de procès-verbal | [Assemblée générale](docs/assemblee-generale.md) |
| **Meublés de tourisme** | Registre des déclarations, point d'information ajouté à l'AG, affiche du hall, projet de résolution si une interdiction est demandée (loi Le Meur) | [Meublés de tourisme](docs/meubles-tourisme.md) |
| **Impayés** | Import du relevé bancaire, rapprochement automatique des paiements, relances graduées jusqu'à la mise en demeure, jamais sans validation du syndic | [Impayés](docs/impayes.md) |
| **Règlement en clair** | Le règlement de copropriété rangé par thèmes, en langage courant ; chaque règle renvoie à son article, et sa citation est vérifiée dans le texte avant que le syndic valide | [Règlement](docs/reglement.md) |
| **Pack nouvel arrivant** | Guide de bienvenue, fiche synthétique et bulletin de choix pour un nouveau propriétaire ; pack remis par le bailleur à son locataire, avec la quote-part de charges du logement | [Nouvel arrivant](docs/nouvel-arrivant.md) |
| **Dossier de vente** | Quand un lot est vendu : fiche synthétique, pré-état daté, plan de travaux et bordereau des documents exigés par la loi, en une archive pour le notaire | [Dossier de vente](docs/dossier-de-vente.md) |
| **Changer de syndic** | Si la copropriété choisit un autre syndic, elle part avec tout : bordereau à signer (article 18-2), état des comptes, tableaux CSV, fiche complète et toutes les archives, en formats ouverts | [Transmission](docs/transmission.md) |
| **Président de séance** | Outil gratuit pour le copropriétaire qui préside l'AG : émargement, pouvoirs, décompte des votes en tantièmes, majorités et passerelles, bilan à comparer avec le PV. Hors ligne, sans compte, rien ne quitte l'appareil | [Président de séance](docs/seance-president.md) |
| **Signalements** | Un QR code dans le hall : les voisins signalent une panne, une fuite ou une dégradation, avec photo, sans compte. Le syndic suit, les voisins voient l'état ; descriptions et photos restent chez le syndic. Rappel du délai de déclaration à l'assurance | [Signalements](docs/signalements.md) |
| **Pack papier** | Courrier, grands caractères, talon de chèque, bulletin papier, affiche du hall : personne n'est laissé de côté | [Pack papier](docs/pack-papier.md) |

<table>
  <tr>
    <td align="center"><img src="docs/apercu_interphone.png" alt="Les copropriétaires, étage par étage, comme sur le tableau d'interphone" width="500"><br><sub>Les copropriétaires, comme sur le tableau d'interphone</sub></td>
    <td align="center"><img src="docs/apercu_page_vote.png" alt="Page de vote d'un copropriétaire" width="205"><br><sub>La page de vote, sur téléphone</sub></td>
  </tr>
</table>

## Démarrage rapide

```bash
cp .env.example .env        # puis remplir MOTEUR_TOKEN et N8N_ENCRYPTION_KEY
docker compose up -d --build
```

L'interface du syndic est sur http://localhost:8000/app, le moteur répond sur http://localhost:8000/docs, n8n sur http://localhost:5678. Le pas-à-pas complet (workflows n8n, sans Docker, démonstration) est dans [docs/installation.md](docs/installation.md), et la liste des routes dans [docs/api.md](docs/api.md).

## Architecture

```
                                     ┌──────────────────────────┐
  navigateur du syndic ────────────► │  /app : interface web    │
  (session, mot de passe)            ├──────────────────────────┤
┌─────────────┐   HTTP + X-API-Key   │                          │
│    n8n      │ ───────────────────► │  moteur (Python/FastAPI) │
│ orchestrer, │ ◄─────────────────── │  valider, calculer,      │
│ mails,      │     JSON + PDF       │  générer les documents   │
│ validation  │                      │                          │
└─────────────┘                      └──────────────────────────┘
                                        ▲              │
                              config/*.yaml       out/ et data/
                              (une fiche par copro)  (PDF, dossiers, votes)
```

| Dossier | Contenu |
|---|---|
| `config/` | Une fiche par copro. `mimosas.yaml` est la copro de démonstration, commentée |
| `core/` | Le socle : calculs, règles, documents PDF. Chaque module se lance aussi en ligne de commande |
| `moteur/` | L'API HTTP, la page de vote et l'image Docker |
| `workflows/` | Les workflows n8n à importer |
| `tests/` | Les tests (`python -m pytest tests/`) |

**Technologies** : Python, FastAPI, ReportLab, n8n, Docker, et Mistral pour l'IA.

## Les garde-fous

- **Le syndic valide tout.** Aucun document ne part et aucune décision n'est prise sans lui.
- **L'argent est exact.** Montants en décimal, jamais en flottant, et répartition au centime sans perte.
- **L'IA reste neutre.** Elle décrit les devis sans en recommander aucun, et le syndic valide chaque résumé.
- **Le droit est une aide, pas un avis.** Les règles appliquées citent leurs articles et renvoient vers l'ADIL ; le procès-verbal signé reste la seule référence.
- **Souveraineté.** IA française (Mistral), sources publiques françaises, hébergement prévu en Europe.

## Données personnelles

- Les fiches des vraies copros, et les dossiers `out/` et `data/`, sont exclus du dépôt (`.gitignore`).
- Le moteur n'est exposé que sur `127.0.0.1` et sur le réseau interne Docker.
- En production : hébergement en Europe, HTTPS, sauvegardes chiffrées.

## Comment ce projet est construit

Mitoyen est développé avec l'aide d'une IA (Claude, d'Anthropic), qui a écrit une grande partie du code.
Mon rôle : définir le besoin et le périmètre, choisir le cadre juridique et l'architecture,
tester, déployer et faire évoluer l'outil. Chaque brique est relue, testée et documentée avant publication.

## Contribuer

Les signalements de bugs, d'erreurs juridiques et les idées sont les bienvenus. Les contributions de code sont acceptées sous un accord de contribution : voir [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

AGPL-3.0. L'auteur se réserve la possibilité de proposer aussi Mitoyen sous d'autres conditions ; la version AGPL reste disponible.

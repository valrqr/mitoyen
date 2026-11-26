# L'interface du syndic

[← Retour à l'accueil](../README.md)

Le moteur sert aussi une interface web, à l'adresse `/app`. Pas d'application à installer : un navigateur suffit, sur ordinateur, tablette ou téléphone.

<p align="center"><img src="apercu_interface.png" alt="Tableau de bord" width="760"></p>

## Les écrans

| Écran | Ce qu'on y fait |
|---|---|
| **Tableau de bord** | La liste de ce qui est à faire, du plus urgent au moins pressé, rédigée en phrases : paiements à confirmer, relances à préparer, convocations à notifier, appel de fonds à préparer, contrats et diagnostics. À côté, trois chiffres : impayés, prochaine AG, fonds de travaux |
| **Impayés** | Importer le relevé bancaire ; rattacher un paiement ou l'écarter en un clic ; préparer une relance, l'ouvrir, la marquer envoyée |
| **Appels de fonds** | Les quatre trimestres de l'exercice : préparer le projet, relire le récapitulatif, valider les avis |
| **Assemblées générales** | Préparer une AG (l'ordre du jour habituel est proposé), voir son calendrier légal, ouvrir les formulaires de vote, la feuille de présence, le procès-verbal |
| **Travaux** | Un dossier par chantier : ajouter les devis (montant, validité, PDF), les voir dans leur ordre d'arrivée sans classement ni recommandation, la quote-part de chacun selon chaque devis, qui doit décider et selon quelle majorité, le comparatif à joindre à la convocation |
| **Plan de travaux** | Le financement des dix ans du plan en un graphique : la part payée par le fonds, la part à appeler en plus. Un simulateur recalcule tout quand on change la cotisation ou la hausse des prix. Pour chaque ligne : ouvrir le dossier de travaux, la reporter, la marquer réalisée |
| **Signalements** | Le lien de la copropriété et l'affiche du hall avec son QR code ; les signalements des voisins, urgents d'abord, avec description, photo et contact ; l'état et une note visible des voisins à mettre à jour ; le délai de déclaration à l'assurance pour les fuites et les dégradations |
| **Copropriétaires** | Présentés étage par étage, comme sur le tableau d'interphone du hall : lots, mail ou courrier, grands caractères, aidant, retard éventuel. Un clic sur un nom ouvre sa fiche : coordonnées, mail ou courrier (avec la trace de la demande de papier), grands caractères, proche aidant (avec la date de son accord écrit). « Enregistrer un changement de propriétaire » inscrit le nouveau propriétaire après une vente, une succession ou une donation |
| **Documents** | Affiche du hall, fiche synthétique, plan de travaux, règlement en clair (import, relecture, validation, lien de consultation), packs de bienvenue, dossier de vente, déclarations de meublés de tourisme, dossier de transfert vers un autre syndic |

<p align="center"><img src="apercu_interphone.png" alt="Les copropriétaires, comme sur le tableau d'interphone" width="760"></p>

<p align="center"><img src="apercu_plan_interface.png" alt="Le plan de travaux : financement année par année et simulateur de cotisation" width="760"></p>

## Modifier la fiche sans toucher au fichier

La fiche de la copropriété (`config/<copro>.yaml`) reste la base. Ce que le syndic modifie dans l'interface
(coordonnées d'un copropriétaire, nouveau propriétaire après une vente) est ajouté à un journal,
`data/<copro>/fiche_modifications.json`, rejoué à chaque lecture de la fiche :

- le fichier de configuration et ses commentaires ne sont jamais réécrits ;
- chaque modification est datée, avec son motif : c'est la trace du syndic bénévole ;
- chaque modification est contrôlée sur la fiche complète avant d'être enregistrée (adresse électronique
  valide, accord écrit pour un proche aidant, un seul vendeur par changement…) ; si la fiche devenait
  incohérente, rien n'est enregistré et un message dit pourquoi ;
- un ancien copropriétaire n'est jamais effacé : il garde ses comptes (et une éventuelle dette de vendeur),
  mais ne reçoit plus les envois de la copropriété ;
- le parcours de vente (Documents → Dossier de vente) mène directement au changement de propriétaire,
  lots et date de l'acte déjà remplis.

« Télécharger la fiche à jour » produit le YAML complet (sans les commentaires), pour l'archiver ou remplacer
le fichier de configuration. Les coordonnées bancaires et le prélèvement ne se modifient pas dans l'interface,
et aucun code d'accès n'est jamais demandé.

## Choix de conception

- **Deux polices, deux publics.** L'outil du syndic utilise Barlow, inspirée de la signalétique : fine, nette, en 16 px. La page de vote en ligne et les documents envoyés par courrier utilisent Atkinson Hyperlegible, dessinée pour les personnes malvoyantes. Les documents reçus par mail et les documents collectifs (affiches, PV, fiche synthétique) restent en Helvetica.
- **La charte des documents.** Le noir du logo, du blanc, un gris pierre ; l'orange est réservé aux chiffres importants, comme sur les PDF.
- **Rien d'externe.** Les polices et htmx (qui rend les boutons actifs sans recharger la page) sont servis par l'application elle-même : aucun appel à un service tiers.
- **Neutre sur les devis.** Les devis s'affichent dans leur ordre d'arrivée ; aucun n'est surligné, classé ni recommandé. La fourchette des prix et l'écart à l'estimation du plan sont donnés sans désigner d'entreprise : le choix revient au conseil syndical et à l'assemblée.
- **Le même principe que le moteur.** L'interface ne fait rien que le syndic n'ait demandé : elle prépare, il valide.

## Connexion et sécurité

| Réglage (`.env`) | Rôle |
|---|---|
| `INTERFACE_MOT_DE_PASSE` | Le mot de passe du syndic. Vide : `MOTEUR_TOKEN` sert de mot de passe |
| `INTERFACE_HTTPS` | `1` en production derrière HTTPS : le cookie de session n'est alors envoyé qu'en HTTPS |
| `INTERFACE_SECRET` | Facultatif : la clé qui signe les sessions (sinon dérivée de `MOTEUR_TOKEN`) |

La connexion ouvre une session signée de 8 heures. Elle donne accès aux mêmes routes que la clé d'API, ce qui permet d'ouvrir les PDF depuis l'interface. Le cookie est en `SameSite=Lax` : un formulaire posté depuis un autre site n'emporte pas la session.

## Modules complémentaires

Un module extérieur au moteur peut s'y brancher sans le modifier : `interface.ajouter_module(rubriques=…, taches=…, gabarits=…)` ajoute des rubriques à la barre latérale, des tâches à la liste « à faire » du tableau de bord et un dossier de gabarits ; un gabarit qui étend `base.html` peut charger ses styles dans le bloc `tete`. Ses routes s'ajoutent à l'application FastAPI (`app.include_router`).

## Essayer

```bash
python scripts/demo_interface.py
MOTEUR_DATA_DIR=demo/data MOTEUR_OUT_DIR=demo/out INTERFACE_MOT_DE_PASSE=demo uvicorn moteur.api:app --reload
```

Ouvrir http://localhost:8000/app/mimosas?au=2027-05-20, mot de passe `demo`. Le paramètre `au` fixe la date de la démonstration : au 20 mai 2027, des paiements attendent confirmation, des relances sont à préparer, les convocations de l'AG du 12 juin doivent partir, et le dossier de la porte de hall compte trois devis dont un expiré. Un lien dans la barre latérale ramène à la date du jour.

## Ce qui viendra

Les sondages du conseil syndical sur les devis restent pour l'instant accessibles par l'API. La tenue de séance d'AG sur tablette et le suivi de chantier feront partie d'une offre complémentaire.

# Les routes du moteur

[← Retour à l'accueil](../README.md)

L'interface web du syndic est servie sous `/app` (voir [interface.md](interface.md)). Toutes les routes demandent l'en-tête `X-API-Key: <MOTEUR_TOKEN>`, sauf `/sante` et les pages de vote personnelles. La documentation interactive complète est servie par le moteur sur `/docs`.

## Socle

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/sante` | Le moteur répond-il ? (sans clé) |
| GET | `/copros` | Fiches disponibles |
| GET | `/copros/{copro}/fiche?au=AAAA-MM-JJ` | Validation de la fiche + alertes de l'échéancier |
| GET | `/copros/{copro}/echeancier?au=&horizon=` | Échéances d'une copro : contrats, diagnostics, AG, mandat, avec niveau d'urgence |
| GET | `/echeancier?au=&horizon=` | Échéances de toutes les copros (workflow hebdomadaire) |

## Appels de fonds

| Méthode | Route | Rôle |
|---|---|---|
| POST | `/copros/{copro}/appels/{exercice}/T{n}?final=false` | Génère avis + récap, renvoie la liste d'envoi |
| GET | `/copros/{copro}/appels/{exercice}/T{n}` | Relit la liste d'envoi |
| GET | `/copros/{copro}/appels/{exercice}/T{n}/recap` | PDF de la récap à signer |
| GET | `/copros/{copro}/appels/{exercice}/T{n}/avis/{id}` | PDF d'un avis |

## Travaux, devis et vote

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/copros/{copro}/travaux` | Dossiers de travaux |
| POST | `/copros/{copro}/travaux` | Créer un dossier (titre, nature, urgence, clé) |
| GET | `/copros/{copro}/travaux/{id}` | Dossier + comparatif des devis + qui décide |
| POST | `/copros/{copro}/travaux/{id}/devis` | Ajouter un devis (formulaire + PDF) |
| GET | `/copros/{copro}/travaux/{id}/comparatif.pdf` | Comparatif PDF à joindre à une convocation |
| POST | `/copros/{copro}/travaux/{id}/resume` | Résumé IA des différences entre devis (brouillon) |
| PUT | `/copros/{copro}/travaux/{id}/resume` | Le syndic valide, et peut corriger, le résumé |
| POST | `/copros/{copro}/travaux/{id}/verifications` | Vérifie les entreprises : registre, BODACC, RGE, assurance décennale |
| POST | `/copros/{copro}/travaux/{id}/sondages` | Ouvre un sondage consultatif et renvoie un lien personnel par copropriétaire |
| GET | `/copros/{copro}/travaux/{id}/sondages/{s}` | Résultats du sondage (en voix et en nombre) |
| POST | `/copros/{copro}/travaux/{id}/ag` | Dépouillement d'AG : une résolution par devis, majorités art. 24, 25, 25-1, 26 |
| POST | `/copros/{copro}/travaux/{id}/conseil` | Vote du conseil syndical (délégation de pouvoirs) |

## Plan de travaux

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/copros/{copro}/plan` | Plan de travaux : lignes et suivi, cotisation minimale légale, points de conformité |
| GET | `/copros/{copro}/plan/projection?cotisation=&indexation=` | Fonds de travaux sur 10 ans, cotisation lissée, quote-part de chaque copropriétaire |
| GET | `/copros/{copro}/plan.pdf?cotisation=&indexation=` | Projection PDF à joindre à la convocation d'AG |
| PUT | `/copros/{copro}/plan/lignes/{ligne}` | Avancement d'une ligne : reportée, réalisée (avec le montant payé), abandonnée |
| POST | `/copros/{copro}/plan/lignes/{ligne}/dossier` | Ouvre le dossier de travaux d'une ligne : devis, comparatif, vote |

## Assemblée générale

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/copros/{copro}/ag/ordre-du-jour-type` | Résolutions habituelles d'une AG annuelle, avec les majorités usuelles |
| POST | `/copros/{copro}/ag` | Prépare une AG : date, lieu, ordre du jour (et une résolution par devis d'un dossier) |
| GET | `/copros/{copro}/ag/{ag}` | AG, calendrier légal et feuille de présence |
| GET | `/copros/{copro}/ag/{ag}/formulaires/{id}` | Formulaire de vote par correspondance pré-rempli d'un copropriétaire |
| PUT | `/copros/{copro}/ag/{ag}/correspondance/{id}` | Enregistre un formulaire reçu (refusé après le délai de 3 jours francs) |
| PUT | `/copros/{copro}/ag/{ag}/presences` | Présents, visio et mandats, avec les contrôles de l'article 22 |
| GET | `/copros/{copro}/ag/{ag}/feuille-presence.pdf` | Feuille de présence à faire émarger |
| POST | `/copros/{copro}/ag/{ag}/depouillement` | Votes en séance et par correspondance → résultat de chaque résolution |
| GET | `/copros/{copro}/ag/{ag}/pv.pdf` | Brouillon de procès-verbal, à relire et faire signer |
| GET | `/copros/{copro}/ag/{ag}/agenda.ics` | Fichier « ajouter à mon calendrier » |
| GET | `/copros/{copro}/ag/{ag}/rappels?au=` | Rappel du jour pour cette AG (J-7 ou J-1), un mail par destinataire |
| GET | `/rappels-ag?au=` | Tous les mails du jour (rappels J-7 et J-1, résultats le lendemain du dépouillement), toutes copros confondues, avec leurs pièces jointes `fichier_pdf` et `fichier_ics` (workflow `rappel_ag.json`) |

## Pack papier

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/copros/{copro}/communication` | Canal de chaque copropriétaire (courrier ou mail), grands caractères, aidants |
| GET | `/copros/{copro}/travaux/{id}/sondages/{s}/bulletins/{cp}` | Bulletin de sondage papier pré-rempli |
| POST | `/copros/{copro}/travaux/{id}/sondages/{s}/bulletins/{cp}` | Saisie d'un bulletin papier reçu, avec sa trace |
| GET | `/copros/{copro}/affiche.pdf?format=A4\|A3` | Affiche du hall, sans aucune donnée personnelle |
| POST | `/copros/{copro}/appels/{exercice}/T{n}/lot-postal` | PDF prêt à imprimer (enveloppes à fenêtre) et manifeste des recommandés |
| GET / POST / PUT | `/copros/{copro}/envois` | Registre des envois : recommandés, dates de notification |
| GET | `/copros/{copro}/ag/{ag}/convocations` | Chaque copropriétaire a-t-il été convoqué dans les délais ? |
| GET | `/copros/{copro}/coproprietaires/{id}/mandat-sepa.pdf` | Mandat de prélèvement SEPA papier pré-rempli |

## Dossier de vente

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/copros/{copro}/fiche-synthetique?au=` | Fiche synthétique en six rubriques, avec la liste des données manquantes |
| GET | `/copros/{copro}/fiche-synthetique.pdf?au=` | La même, en PDF |
| POST | `/copros/{copro}/ventes` | Dossier de vente d'un ou plusieurs lots d'un même vendeur : bordereau, PDF, archive |
| GET | `/copros/{copro}/ventes/{id}.zip` | Archive du dossier, à transmettre au notaire |

## Changer de syndic

| Méthode | Route | Rôle |
|---|---|---|
| POST | `/copros/{copro}/transmission` | Dossier de transfert vers un autre syndic (ZIP). Corps JSON : `successeur`, `successeur_adresse`, `cessation`, et facultatifs `date_soldes`, `solde_courant`, `solde_fonds_travaux` |

## Impayés

| Méthode | Route | Rôle |
|---|---|---|
| POST | `/copros/{copro}/banque/releves` | Import d'un relevé CSV (formulaire, champ `fichier`). Sans doublon, même si les relevés se chevauchent |
| GET | `/copros/{copro}/impayes?au=&detail=` | Rapprochement, comptes des copropriétaires, relances proposées |
| GET | `/copros/{copro}/impayes.pdf?au=` | État des impayés, document interne au syndic et au conseil syndical |
| PUT | `/copros/{copro}/banque/operations/{op}` | `confirme` (avec le copropriétaire), `ignore` ou `annule` |
| POST | `/copros/{copro}/impayes/ajustements` | Solde antérieur, appel de travaux, frais de recouvrement, avoir |
| POST | `/copros/{copro}/relances/{cid}?au=` | Prépare la relance proposée (409 si ce n'est pas le moment) |
| GET | `/copros/{copro}/relances/{id}.pdf` | La lettre |
| PUT | `/copros/{copro}/relances/{id}` | Marque la relance envoyée (date, moyen, date de présentation du recommandé) ou annulée |

## Meublés de tourisme

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/copros/{copro}/meubles-tourisme?au=` | Registre des déclarations, lots à présenter en AG, conditions d'une interdiction |
| POST | `/copros/{copro}/meubles-tourisme/declarations` | Information reçue d'un propriétaire (art. 9-2) ; le point d'AG s'ajoute à la prochaine AG créée |
| PUT | `/copros/{copro}/meubles-tourisme/declarations/{id}` | Fin de la location touristique |
| GET | `/copros/{copro}/meubles-tourisme/affichage.pdf?au=` | Affiche pour les parties communes, sans nom ni numéro de lot |
| GET | `/copros/{copro}/meubles-tourisme/resolution` | Projet de résolution d'interdiction (art. 26 d), si les conditions le permettent |

## Règlement en clair

| Méthode | Route | Rôle |
|---|---|---|
| POST | `/copros/{copro}/reglement` | Importe le règlement (PDF, champ `fichier`) et le découpe en articles |
| POST | `/copros/{copro}/reglement/redaction` | Rédige la version en clair (Mistral), citations vérifiées |
| GET | `/copros/{copro}/reglement` | Thèmes, règles, points écartés, date de validation |
| GET | `/copros/{copro}/reglement-en-clair.pdf?usage=` | Le document ; `usage=true` : les règles de vie pour un locataire |
| GET | `/relais/{copro}/{jeton}` | Page privée du relais pendant l'absence du syndic (sans clé, `noindex`, ouverte de la veille du départ au retour) |
| GET | `/reglement/{copro}/{jeton}` | Page publique du règlement partagé (sans clé ; lien activé par le syndic, `noindex`) |
| GET | `/reglement/{copro}/{jeton}/en-clair.pdf?grand=&usage=` | La version en clair validée, en grands caractères ou en extraits |
| GET | `/reglement/{copro}/{jeton}/texte-integral.pdf` | Le PDF d'origine sans ses propriétés, si le syndic le partage |

## Pack nouvel arrivant

| Méthode | Route | Rôle |
|---|---|---|
| GET | `/copros/{copro}/bienvenue/proprietaire.pdf?lots=&nom=&grand=` | Guide de bienvenue, fiche synthétique et bulletin de choix |
| GET | `/copros/{copro}/bienvenue/locataire.pdf?lots=&grand=` | Pack remis par le bailleur à son locataire, avec la quote-part de charges |

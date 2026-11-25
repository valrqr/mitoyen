# Le dossier de vente en un clic

[← Retour à l'accueil](../README.md)

Quand un copropriétaire vend son lot, l'acquéreur doit recevoir une série de documents, annexés à la promesse de vente (article L. 721-2 du code de la construction et de l'habitation). Tant qu'il ne les a pas, son délai de rétractation ne court pas. Chez un syndic professionnel, ces documents sont facturés, souvent plusieurs centaines d'euros. Dans une copropriété gérée avec Mitoyen, presque tout est déjà dans la fiche : un appel suffit.

## Ce que contient le dossier

| Fichier | Contenu | D'où viennent les données |
|---|---|---|
| `00_bordereau.pdf` | La liste des documents exigés par la loi, avec pour chacun : fourni, joint, à joindre, à compléter | Calculé |
| `01_fiche_synthetique.pdf` | Les six rubriques de la fiche synthétique (décret n° 2016-1822) : identification, syndic, organisation, caractéristiques techniques, équipements, finances | Fiche de la copro, section `comptes_approuves` |
| `02_pre_etat_date.pdf` | Pour les lots vendus : charges du budget et échéancier, charges payées par le vendeur, part du fonds de travaux, état global des impayés et des dettes, travaux votés, ce que le plan de travaux représentera année par année | Fiche, dossiers de travaux, AG, plan ; comptes du vendeur fournis par le syndic |
| `03_plan_travaux.pdf` | La projection du plan pluriannuel de travaux | [Plan de travaux](plan-de-travaux.md) |
| `documents/…` | Ce que le syndic a déposé dans `data/<copro>/documents/` : règlement, procès-verbaux signés, carnet d'entretien, DTG, notice d'information | Reconnus par leur nom : `reglement…`, `pv_…`, `carnet…`, `dtg…`, `notice…` |

La dernière rubrique du pré-état daté est la plus utile à l'acquéreur : il sait, avant de signer, combien le plan de travaux lui coûtera chaque année pour ce lot.

## Ce que Mitoyen ne devine pas

- **Les comptes du vendeur, avant la reprise.** Quand la [comptabilité](comptabilite.md) couvre les exercices demandés, Mitoyen calcule lui-même la quote-part des lots dans les charges réelles des deux derniers exercices, les impayés du vendeur et l'état global du syndicat (impayés, dettes fournisseurs). Pour un exercice antérieur à la reprise dans Mitoyen, le syndic les fournit d'après les comptes de l'ancien syndic, sinon la rubrique est marquée « à compléter ». Ce que le syndic fournit l'emporte toujours.
- **Les documents signés.** Les procès-verbaux d'AG, le règlement de copropriété : Mitoyen les joint s'ils sont déposés, sinon le bordereau les signale à joindre.
- **Une donnée absente de la fiche.** La fiche synthétique liste ce qui manque au lieu de l'inventer.

Si l'acquéreur est déjà copropriétaire, les documents d'organisation de l'immeuble ne sont pas à lui transmettre : le bordereau les marque « déjà détenu ».

## Exemple

```bash
curl -X POST localhost:8000/copros/mimosas/ventes -H "X-API-Key: $MOTEUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"lots": [2, 21], "impayes_vendeur": "0",
       "charges_payees": [{"exercice": 2024, "budget": "1210.40"}, {"exercice": 2025, "budget": "1262.80"}]}'
```

La réponse donne le bordereau, ce qui reste à compléter et le lien de l'archive ZIP. Un dossier par vendeur : plusieurs lots d'un même propriétaire (un appartement et son parking) vont dans le même dossier.

## La fiche synthétique, à part

La fiche synthétique doit aussi être tenue à jour chaque année, dans les deux mois qui suivent l'AG qui approuve les comptes, et mise à disposition de chaque copropriétaire. `GET /copros/{copro}/fiche-synthetique.pdf` la produit à tout moment ; il suffit de mettre à jour la section `comptes_approuves` de la fiche après l'AG.

## Avant l'acte : l'état daté

Le notaire demande au syndic, et à lui seul, l'état daté (décret du 17 mars 1967, art. 5). Chez un syndic professionnel, il peut coûter jusqu'à 380 € TTC (décret n° 2020-153, plafond confirmé par le Conseil d'État le 17 mars 2026). Ici, le syndic bénévole l'établit sans honoraires : **Documents → État daté, certificat et suivi de la vente** (`/app/<copro>/ventes`).

| Partie | Calcul |
|---|---|
| 1. Sommes dues par le vendeur | Soldes de son compte à la date choisie : provisions exigibles de l'exercice, hors budget, impayés des exercices antérieurs (les paiements apurent d'abord les dettes les plus anciennes), fonds de travaux, avances. Ce qu'il a versé en trop sur un compte apure ce qu'il doit sur un autre. |
| 2. Sommes dues par le syndicat au vendeur | Ce qui reste versé d'avance, et sa part des avances (compte 103). |
| 3. Sommes qui incomberont à l'acquéreur | Les provisions de l'exercice pas encore exigibles (elles sont dues par celui qui est copropriétaire à leur date d'exigibilité, art. 6-2), la reconstitution des avances, et une estimation de la part des travaux votés restant à appeler. |
| Annexe | Quote-part des lots dans les budgets et les charges réelles des deux exercices précédents ; procédures en cours, saisies par le syndic. |

Avec l'état daté, Mitoyen joint :
- le **certificat de l'article 20** (loi du 10 juillet 1965) si le vendeur ne doit rien : présenté au notaire, il évite l'avis de mutation ;
- sinon, le **décompte des sommes liquides et exigibles**, qui servira, le cas échéant, à l'opposition.

L'état daté se calcule à partir des comptes : il demande des soldes d'ouverture saisis avant la date choisie.

## Après la vente

L'écran de la vente garde la trace de chaque vente signée (lots, date de l'acte, acquéreur, notaire) et ce qu'il reste à faire :
1. **L'avis de mutation**, que le notaire envoie si le vendeur n'a pas présenté le certificat. À sa réception, Mitoyen affiche le délai d'opposition : **15 jours**, par acte d'un commissaire de justice, dans la limite du décompte. Si le vendeur ne devait rien à la date de l'acte, l'étape est marquée inutile.
2. **Le nouveau copropriétaire dans la fiche** (lots, coordonnées, mode d'envoi) : les appels exigibles après la vente lui seront adressés.

L'acquéreur reçoit son [pack de bienvenue](nouvel-arrivant.md) : guide, fiche synthétique et bulletin de choix (mail ou courrier, prélèvement, proche aidant), préparés à partir des mêmes numéros de lots.

> Aide à la préparation, d'après la loi du 10 juillet 1965 (art. 20) et le décret du 17 mars 1967 (art. 5, 5-1 et 6-2) : à comparer avec les textes sur Légifrance. Le notaire vérifie le dossier. Mitoyen ne donne pas de conseil juridique : en cas de doute, l'ADIL de votre département répond gratuitement.

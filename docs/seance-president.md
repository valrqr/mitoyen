# Président de séance

Un outil gratuit pour le copropriétaire élu président de séance d'une assemblée générale. Il pointe les présents et les pouvoirs, compte les votes en tantièmes, applique les majorités et produit un bilan à comparer avec le procès-verbal du syndic.

Il s'adresse à toutes les copropriétés, quel que soit leur syndic : professionnel, bénévole ou coopératif.

> Aide au calcul : seul le procès-verbal signé fait foi. Mitoyen ne fournit pas de conseil juridique ; en cas de doute, adressez-vous à l'ADIL de votre département.

## Adresse

`mitoyen.app/seance`, qui redirige vers `seance.mitoyen.app`, où l'outil est hébergé en simples fichiers.

## Les quatre étapes

| Étape | Ce qu'on fait |
|---|---|
| **1. Préparer** | Coller la liste des copropriétaires, vérifier l'aperçu, puis ajouter les résolutions et leur majorité (article 24, 25 ou 26). |
| **2. Émargement** | Pour chacun : absent, présent, représenté (nom du mandataire) ou par correspondance (on saisit les votes du formulaire). |
| **3. Votes** | Pour chaque résolution, marquer les « contre » et les abstentions, puis « Les autres votent pour ». Le résultat s'affiche en direct, avec la passerelle et le second vote quand la loi les permet. |
| **4. Bilan** | Tableau des résultats, noms et voix des opposants et abstentionnistes, liste de points à comparer avec le procès-verbal. Imprimable. |

## Récupérer la liste sans tout taper

Pour 20 ou 25 copropriétaires, on ne saisit rien ligne par ligne : on colle une liste entière.

| Source | Comment |
|---|---|
| Photo de la feuille de présence ou de la répartition des charges | Texte en direct (iPhone) ou Google Lens (Android) : copier le texte reconnu, le coller dans l'outil |
| PDF ou tableur du syndic | Sélectionner les lignes et les coller telles quelles |
| Copie de l'année précédente | « Reprendre une liste enregistrée » : copropriétaires et résolutions reviennent, sans les votes ; on corrige les ventes de l'année |

La lecture est tolérante : sur chaque ligne, le dernier nombre est pris comme tantièmes (« 125 », « 125/1000 », « 125 tantièmes ») ; les numéros de lot (« Lot 12 ») et de compte en tête de ligne sont retirés ; les lignes de titre et de total sont ignorées ; un même nom sur plusieurs lignes (plusieurs lots) est regroupé et ses tantièmes additionnés. Un aperçu affiche la liste comprise et son total avant tout ajout, et signale un total différent de la base (par exemple 990 sur 1 000).

La reconnaissance de texte n'est pas intégrée à l'outil : celle des téléphones est meilleure, et elle alourdirait la page d'une dizaine de mégaoctets, ce qui nuirait au fonctionnement hors ligne.

## Les règles appliquées

| Règle | Texte |
|---|---|
| Majorités des articles 24, 25 et 26 | Loi du 10 juillet 1965 |
| Passerelles : second vote à l'article 24 (25-1) ou 25 (26-1) | Loi, art. 25-1 et 26-1 |
| Réduction des voix d'un copropriétaire majoritaire | Loi, art. 22 |
| 3 pouvoirs au plus par mandataire, sauf si le total ne dépasse pas 10 % des voix ; le syndic ne peut pas en recevoir | Loi, art. 22 |
| Formulaire par correspondance écarté si l'auteur est présent ou représenté | Décret du 17 mars 1967, art. 14-1 |
| Votant par correspondance compté défaillant si la résolution est amendée | Loi, art. 17-1 A |

Les règles sont dans `seance/regles.js`. Un test (`tests/test_seance_parite.py`) vérifie, sur 400 cas tirés au hasard, qu'elles donnent les mêmes résultats que le moteur Python (`core/vote.py`).

Limite de la première version : toutes les résolutions sont votées sur les tantièmes des charges communes générales. Les résolutions sur des charges spéciales (ascenseur, escalier) ne sont pas encore prises en charge.

## Données

- Tout reste dans le navigateur de l'appareil (stockage local). Rien n'est envoyé, il n'y a pas de compte.
- « Enregistrer une copie » télécharge un fichier JSON ; « Reprendre une copie » le recharge.
- « Tout effacer » vide l'appareil, avec une confirmation.

## Hors ligne

Une fois ouverte une première fois (avec du réseau), la page est gardée sur l'appareil par un service worker et fonctionne sans connexion. Elle peut être ajoutée à l'écran d'accueil comme une application.

## Fichiers

```
seance/
├── index.html            la page
├── app.js                l'interface (quatre étapes)
├── regles.js             les règles de vote, sans interface
├── style.css             Barlow, encre et blanc ; l'orange marque les résolutions adoptées
├── sw.js                 fonctionnement hors ligne
├── manifest.webmanifest  installation sur l'écran d'accueil
├── icone.svg, icone-192.png, icone-512.png
└── polices/              Barlow (licence OFL), servie avec l'outil
```

## Essayer en local

```bash
python3 -m http.server 8000 --directory seance
# puis ouvrir http://localhost:8000
```

Le service worker ne s'active qu'en HTTPS : en local, la page fonctionne mais pas hors ligne.

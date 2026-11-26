# Le règlement de copropriété en clair

[← Retour à l'accueil](../README.md)

Un règlement de copropriété fait souvent quarante pages de langage notarial, et peu de copropriétaires l'ont lu. Mitoyen en tire une version lisible, rangée par thèmes, où **chaque règle renvoie à l'article d'où elle vient**.

## Comment ça marche

| Étape | Qui | Ce qui se passe |
|---|---|---|
| 1. Import | Le syndic | Il charge le PDF du règlement (texte sélectionnable, modificatifs fusionnés). Mitoyen le découpe article par article |
| 2. Rédaction | L'IA (Mistral) | Elle range les règles en dix thèmes, en langage courant, et justifie chacune par une courte citation du texte |
| 3. Vérification | Mitoyen | Chaque citation doit figurer mot pour mot dans l'article cité ; une règle sans appui, ou qui cite un article inexistant, est écartée et signalée |
| 4. Relecture | Le syndic | Une règle par ligne, terminée par ses articles : il corrige, ajoute, retire, puis valide |
| 5. Diffusion | Mitoyen | La version validée rejoint le pack nouvel arrivant ; les règles de vie (sans les charges) rejoignent le pack locataire |

Les dix thèmes : destination de l'immeuble, location et meublés de tourisme, parties communes, travaux, façades et balcons, bruit, animaux, caves et stationnement, sécurité et entretien, charges.

## Ce que dit le document

Le PDF « Le règlement en clair » se termine par un rappel commun à toutes les copropriétés : **si une règle n'est pas respectée**, le syndic la fait respecter (loi du 10 juillet 1965, art. 18) par un rappel puis une mise en demeure ; une action en justice au nom de la copropriété se décide en AG (décret du 17 mars 1967, art. 55), sauf exceptions comme le référé ; un copropriétaire peut agir seul pour la jouissance de son lot ; le bailleur répond de son locataire.

La version en clair **ne remplace pas le règlement** : en cas de doute, c'est le texte du règlement qui fait foi. Elle ne dit pas non plus si une clause est valable. Pas un conseil juridique : l'ADIL répond gratuitement.

## Le partager avec les copropriétaires

Depuis la page du règlement, le syndic crée un **lien de consultation**, à mettre dans un mail, une convocation ou l'affiche du hall. La page montre la version en clair par thèmes, avec trois PDF : la version complète, la version en grands caractères et les extraits pour un locataire.

- **Le texte intégral** s'ajoute sur option : le syndic vérifie d'abord qu'il ne contient ni code d'accès ni coordonnées personnelles. Le PDF est réenregistré sans ses propriétés (auteur, logiciel).
- Tant que la version en clair n'est pas validée, seul le texte intégral peut être partagé.
- Le lien est désactivé par défaut, n'est pas indexé par les moteurs de recherche, et se coupe ou se renouvelle à tout moment : l'ancien lien cesse alors de fonctionner.

## Essayer

La démonstration contient un règlement fictif (`exemples/reglement/reglement_mimosas.pdf`, 16 articles) et sa version en clair validée : `/app/mimosas/reglement`.

```bash
curl -H "X-API-Key: $MOTEUR_TOKEN" -F fichier=@exemples/reglement/reglement_mimosas.pdf localhost:8000/copros/mimosas/reglement
curl -X POST -H "X-API-Key: $MOTEUR_TOKEN" localhost:8000/copros/mimosas/reglement/redaction    # MISTRAL_API_KEY requise
curl -H "X-API-Key: $MOTEUR_TOKEN" localhost:8000/copros/mimosas/reglement-en-clair.pdf -o reglement_en_clair.pdf
```

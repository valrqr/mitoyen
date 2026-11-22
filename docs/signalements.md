# Signalements des copropriétaires

Une panne d'éclairage, une fuite dans la cave, une porte qui ferme mal : les copropriétaires (et les locataires) le signalent depuis un QR code affiché dans le hall. Le syndic reçoit le signalement dans son tableau de bord, le suit, et les voisins voient où il en est.

## Côté voisins : `/signaler/<copro>/<jeton>`

Une page sans compte, sans JavaScript, lisible sur téléphone :

1. **Danger immédiat ? Appelez d'abord.** Avant tout formulaire : 112 ou 18, le numéro Urgence Sécurité Gaz de GRDF (0 800 47 33 33, gratuit, 24 h/24), et les numéros d'astreinte des prestataires déclarés dans la fiche (`telephone_astreinte` dans un contrat).
2. **Le formulaire** : catégorie, lieu, ce qui a été constaté, gênant ou urgent, une photo et un contact facultatifs.
3. **Déjà signalé** : la liste des signalements en cours ou réglés, pour éviter les doublons.

| Les voisins voient | Seul le syndic voit |
|---|---|
| Catégorie, lieu, date, état (reçu, en cours, réglé), note publique du syndic | Description, photo, contact |

## Les garde-fous

| Risque | Parade |
|---|---|
| Un signalement qui vise une personne | Le formulaire rappelle de décrire des faits et de ne nommer personne ; la description n'est jamais publiée |
| Une photo qui trahit qui l'a prise et où | La photo est réencodée : les métadonnées (position GPS, appareil) disparaissent ; elle est réduite à 1 600 pixels |
| Une urgence traitée comme un formulaire | Les numéros d'urgence passent avant le formulaire, sur la page comme sur l'affiche |
| Le lien qui circule hors de l'immeuble | Le syndic crée un nouveau lien en un clic ; l'ancien cesse de fonctionner |
| Des robots | Un champ piège invisible, et 30 signalements par jour au plus par copropriété |

## Côté syndic : rubrique « Signalements »

- **Le lien et l'affiche du hall** : une page A4 en Atkinson Hyperlegible avec le QR code, les numéros d'urgence et la voie papier (la boîte aux lettres du syndic).
- **Les signalements en cours**, urgents d'abord : description, photo, contact, état et note publique à mettre à jour.
- **Le tableau de bord** affiche les signalements urgents, les nouveaux, et les déclarations d'assurance à faire.

### Délai de déclaration à l'assurance

Pour une fuite ou un dégât des eaux, et pour une dégradation ou un acte de vandalisme, Mitoyen affiche la date limite pour déclarer le sinistre à l'assureur de l'immeuble. Le Code des assurances (art. L113-2) impose au contrat un délai d'au moins 5 jours ouvrés (2 jours pour un vol). Si le contrat prévoit plus, le champ `delai_declaration_jours_ouvres` du contrat d'assurance dans la fiche l'indique. Les jours fériés ne sont pas retirés du calcul : la date affichée garde donc une marge. Un bouton « C'est déclaré » fait disparaître le rappel.

## Stockage

`data/<copro>/signalements/signalements.json` et les photos à côté. Ces fichiers contiennent des données personnelles (contact, photos) : ils restent hors du dépôt, comme tout `data/`.

## API

| Route | Accès |
|---|---|
| `GET` et `POST /signaler/{copro}/{jeton}` | Lien secret de la copropriété |
| `GET /app/{copro}/signalements` | Syndic connecté |
| `POST /app/{copro}/signalements/{id}` (état, note publique) | Syndic connecté |
| `POST /app/{copro}/signalements/{id}/assurance` | Syndic connecté |
| `GET /app/{copro}/signalements/{id}/photo.jpg` | Syndic connecté |
| `GET /app/{copro}/signalements/affiche.pdf` | Syndic connecté |
| `POST /app/{copro}/signalements/lien` (nouveau lien) | Syndic connecté |

# Comptabilité en partie double

Toute copropriété qui sort du régime simplifié tient une comptabilité d'engagement en partie double. C'est le cas au-delà de 5 lots principaux, dès que le budget moyen atteint 15 000 € sur trois exercices (loi du 10 juillet 1965, art. 14-3). Le cadre est fixé par le décret n° 2005-240 et l'arrêté du 14 mars 2005. Le module `core/compta.py` tient ces comptes **sans rien faire saisir deux fois**.

> Aide à la gestion, pas un conseil comptable. Le plan comptable reprend la nomenclature de l'arrêté du 14 mars 2005 : avant un usage réel, comparez-le au texte en vigueur sur Légifrance, surtout pour les comptes du fonds de travaux. L'ADIL du département renseigne gratuitement.

## L'image : le cahier en deux colonnes

Chaque euro est écrit deux fois : d'où il vient, où il va. Un appel de fonds, par exemple, s'écrit « le copropriétaire doit 300 € » et « le syndicat a appelé 300 € de provisions ». À la fin, les deux colonnes du cahier doivent avoir le même total. Sinon, il y a une erreur quelque part.

## D'où viennent les écritures

| Ce que Mitoyen connaît déjà | Écriture produite |
| --- | --- |
| Soldes repris de l'ancien syndic | Banque, comptes des copropriétaires, fournisseurs et fonds de travaux au premier jour |
| Appel de fonds validé | Débit 4501 (copropriétaire) / crédit 701 (provisions). Pour le fonds de travaux : débit 4505 / crédit 105 |
| Ajustement du recouvrement (travaux, frais, avoir) | Compte du copropriétaire / 702, 714 ou 701 |
| Facture saisie | Débit du compte de charge (611, 614, 616…) / crédit 401 (fournisseur) |
| Paiement d'un copropriétaire rapproché | Débit 512 (banque) / crédit 4501 |
| Débit du relevé affecté à une facture | Débit 401 / crédit 512 |
| Débit payé directement (frais bancaires) | Débit du compte de charge / crédit 512 |
| Opération bancaire pas encore expliquée | Compte 471 (attente) |

Le compte 471 est le garde-fou : rien n'est jamais « ajusté » pour que les chiffres tombent juste. Un écart reste visible tant qu'il n'est pas expliqué.

## La date de reprise

Les soldes d'ouverture sont ceux du premier jour tenu dans Mitoyen. Tout ce qui précède (opérations du relevé, appels de fonds, factures) est déjà dans ces soldes : Mitoyen l'ignore, pour ne rien compter deux fois. Une facture antérieure restée impayée se reprend dans les soldes, sur la ligne de son fournisseur.

## L'écran « Comptabilité »

Dans l'interface du syndic, rubrique **Comptabilité** (`/app/<copro>/comptes`) :

| Bloc | Ce qu'on y fait |
| --- | --- |
| Avant d'arrêter les comptes | Les contrôles ci-dessous, verts ou orange, avec l'écart chiffré |
| Soldes d'ouverture | Saisis une fois : banque, fonds de travaux, compte de chaque copropriétaire, factures fournisseurs restant dues. Corrigeables ensuite |
| Dépenses du relevé à expliquer | Chaque débit du compte d'attente : rattaché à une facture saisie, ou passé en dépense directe dans un compte de charge |
| Factures | Saisie (fournisseur, date, montant TTC, nature de la charge) et liste, avec « réglée » ou « pas encore » |
| Balance | Par classe, chaque compte avec ses comptes auxiliaires repliés (copropriétaires par leur nom) ; un clic ouvre le grand livre du compte |

Les encaissements non rattachés à un copropriétaire se règlent dans **Impayés**, là où se fait le rapprochement des paiements.

## Contrôles avant d'arrêter les comptes

1. Le total des débits égale le total des crédits.
2. Le compte 512 égale le solde du relevé bancaire.
3. Le compte d'attente 471 est soldé.
4. Les soldes d'ouverture sont saisis.

## Étapes

| Étape | Contenu | État |
| --- | --- | --- |
| 1. Socle | Plan comptable, journal recalculé, balance, grand livre, contrôles | Fait |
| 2. Interface | Saisie des factures et des soldes d'ouverture, affectation des dépenses, balance à l'écran | Fait |
| 3. Annexes | Les 5 annexes réglementaires jointes à la convocation de l'AG (état financier, compte de gestion général, budget voté et réalisé, travaux, opérations non soldées) | À faire |
| 4. Clôture | Répartition des charges réelles par clé et par lot, régularisation des provisions, verrouillage de l'exercice approuvé | À faire |
| 5. Export | Journal et balance en CSV pour un expert-comptable ou un contrôleur des comptes | À faire |

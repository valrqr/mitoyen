# L'assemblée générale sans papier

[← Retour à l'accueil](../README.md)

Mitoyen prépare toute l'assemblée générale, du calendrier au procès-verbal, dans le respect de la loi du 10 juillet 1965 et du décret du 17 mars 1967 :

| Étape | Ce que fait Mitoyen |
|---|---|
| **Calendrier** | Dates limites de convocation (21 jours), de réception des votes par correspondance (3 jours francs), de notification du procès-verbal (1 mois) ; alerte si l'AG annuelle dépasse les 6 mois après la clôture |
| **Vote par correspondance** | Un formulaire pré-rempli par copropriétaire, sur la structure du modèle de l'arrêté du 2 juillet 2020 ; les formulaires arrivés hors délai sont refusés |
| **Convocations** | Le registre des envois vérifie que chaque copropriétaire a été convoqué à temps |
| **Rappels** | Un mail à J-7 (ordre du jour, date limite du vote par correspondance) et la veille, avec le fichier « ajouter à mon calendrier » ; voir ci-dessous |
| **Présences et mandats** | Présents, visio, représentés ; le syndic ne peut pas recevoir de mandat, et au-delà de 3 mandats le total ne doit pas dépasser 10 % des voix |
| **Feuille de présence** | Avec la date de réception de chaque formulaire ; celui d'un copropriétaire finalement présent est écarté |
| **Dépouillement** | En séance, on note qui vote contre et qui s'abstient ; une résolution amendée transforme le « pour » par correspondance en défaillance ; majorités 24, 25 et 26, passerelles vers un second vote (art. 25-1 et 26-1), clés spéciales ; les points d'information ne sont pas votés |
| **Procès-verbal** | Brouillon avec les noms et les voix des opposants, abstentionnistes et défaillants, et la liste des copropriétaires à qui le notifier |

<p align="center"><img src="apercu_formulaire_vote.png" alt="Formulaire de vote par correspondance pré-rempli" width="420"></p>

## Les rappels et l'agenda

La convocation est notifiée au moins 21 jours avant : c'est loin, et une AG s'oublie. Le workflow n8n `rappel_ag.json` envoie chaque matin les rappels du jour :

| Quand | Contenu |
|---|---|
| **7 jours avant** | Date, lieu, lien de visio si l'AG l'a autorisée, ordre du jour, et la date limite du vote par correspondance tant qu'elle n'est pas passée |
| **La veille** | « C'est demain », l'heure et le lieu ; pour ceux qui ne pourront pas venir, la possibilité de donner pouvoir |

Chaque mail porte un fichier `.ics` : un clic ajoute la réunion à l'agenda, quel qu'il soit (Apple, Google, Outlook, Thunderbird), avec une alerte la veille. Le fichier décrit le fuseau de Paris, donc l'heure reste juste partout.

Quelques attentions :

- un copropriétaire qui a déjà voté par correspondance lit que son vote est enregistré, et que s'il vient, c'est son vote en séance qui comptera ;
- ceux qui reçoivent leurs documents par courrier n'ont pas de mail : le syndic reçoit leur liste (un mot dans la boîte aux lettres suffit, l'affiche du hall annonce déjà la date) ;
- le proche aidant est prévenu, même si le copropriétaire reçoit tout par courrier ;
- chaque rappel précise qu'il ne remplace pas la convocation officielle.

> Le formulaire reprend la structure et les mentions du modèle officiel : avant un usage réel, comparez-le à l'annexe de l'arrêté du 2 juillet 2020 sur Légifrance. Une case laissée vide n'est pas comptée et signalée au bureau, la loi ne disant pas comment la traiter. Le procès-verbal signé reste la seule référence.

## Combien ça me coûte ?

Avant de voter, chaque copropriétaire voit ce qu'une résolution lui coûterait à lui, et pas seulement le montant total.

- **Sur le formulaire de vote par correspondance**, sous chaque résolution chiffrée : « Votre part : 216,00 € en 2 appels de 108,00 € », ou « vous n'êtes pas concerné » si ses lots n'ont pas de tantièmes dans la clé de la résolution.
- **Une page à joindre à la convocation**, « Ce que chaque résolution vous coûterait » : le montant total, la part du copropriétaire et les échéances. Le total des dépenses ponctuelles est indiqué ; quand plusieurs devis sont proposés pour les mêmes travaux, il ne compte que le plus cher.

D'où viennent les montants :

| Résolution | Montant |
|---|---|
| Question saisie avec un montant (`Remplacement de la porte du hall ; 4 800 € ; 2 appels`) | Le montant TTC saisi, en une ou plusieurs échéances (12 au plus) |
| Devis d'un dossier de travaux | Le montant TTC du devis |
| Cotisation au fonds de travaux | La cotisation annuelle de la fiche |
| Budget prévisionnel | Le budget de l'exercice en cours, présenté comme tel : le projet joint à la convocation fait foi |

La part est calculée lot par lot selon les tantièmes de la clé de la résolution, comme sur un avis d'appel de fonds (méthode du plus fort reste : la somme des parts retombe toujours sur le total). Les échéances suivent les dates d'exigibilité habituelles de la fiche, à partir de la première qui suit l'AG ; pour le budget et le fonds de travaux, à partir du début de l'exercice suivant. Elles sont indicatives : l'assemblée fixe le calendrier des appels.

API : `GET /copros/{copro}/ag/{ag}/votre-part` (toutes les parts, JSON) et `GET /copros/{copro}/ag/{ag}/votre-part/{id}` (le PDF d'un copropriétaire).

## L'AG en bref

La plupart des copropriétaires ne lisent ni la convocation ni le procès-verbal. « L'AG en bref » leur dit l'essentiel sur une page, en une minute.

- **Avant l'AG**, à joindre à la convocation : la date et le lieu, le dernier jour pour voter par correspondance, la part du lecteur si toutes les dépenses sont adoptées, la liste des points avec sa part pour chacun, et les trois façons de participer (venir, donner un pouvoir, voter par correspondance).
- **Après le dépouillement** : le nombre de décisions adoptées et rejetées, ce que le lecteur va payer et la date du prochain appel, chaque point avec son issue, puis « Et maintenant ? » (appels de fonds, procès-verbal, délai de contestation de deux mois de l'article 42).

Le texte est construit à partir des résultats, sans IA : aucune reformulation ne peut trahir une décision. La page dit qu'elle ne remplace ni la convocation ni le procès-verbal signé. Elle suit les préférences de chacun : police Atkinson Hyperlegible pour les envois papier, grands caractères sur demande.

**Les échéances votées dans son agenda.** Après le dépouillement, un fichier `.ics` reprend, pour chaque copropriétaire, les échéances des dépenses ponctuelles adoptées : un événement par appel, avec une alerte une semaine avant. Le budget et le fonds de travaux n'y figurent pas, puisqu'ils passent déjà par les appels trimestriels habituels. Dates et montants sont indicatifs : l'avis d'appel de fonds fait foi.

API : `GET /copros/{copro}/ag/{ag}/en-bref/{id}` (PDF, avant ou après selon que le dépouillement est fait) et `GET /copros/{copro}/ag/{ag}/echeances/{id}.ics`.

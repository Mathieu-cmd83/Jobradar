# Bilan des sources — 8 octobre 2026

Les 23 enseignes sont celles du dictionnaire `SITES` de la version Git `2920f5b` et de la liste `SOURCES` de `ee8dfc7`. Aucune enseigne n’a été ajoutée pour compléter artificiellement le nombre 23, retirée silencieusement ou classée par priorité commerciale.

## Résultat réel

**1 agence sur 23 connectée : Triangle Intérim, avec une couverture partielle.** L’API WordPress publique et les deux permaliens ont été interrogés sans compte candidat, sans mot de passe et sans authentification. La recherche `Toulon` renvoie deux posts exploitables : « Tuyauteur nucleaire H/F en grand deplacement » et « Stagiaire 2 mois ». Le lieu structuré indique Toulon / 83 / Var, le contrat indique Intérim et le critère de temps de travail indique Temps plein. Le titre « Stagiaire » n’est pas utilisé pour remplacer le contrat déclaré par la source.

**Emploi-Territorial est une source complémentaire, pas une des 23 agences.** Son RSS département 083 a livré 100 offres. Le connecteur extrait désormais le lieu de travail, l’employeur, le temps de travail et la date limite de candidature à partir des champs du flux.

Le test réel du 8 octobre à **16 h 41, heure de Paris**, exécuté avec une base SQLite temporaire neuve, a importé 102 offres et exécuté l’application Streamlit sans mocks : trois onglets, compteur de 102 et aucune exception ni erreur applicative. Voir [les preuves structurées](live_validation.json). Ces nombres décrivent ce test précis, pas une disponibilité future ni une couverture exhaustive.

**22 agences restent non connectées : 20 après constat de restrictions de réutilisation/extraction, 2 bloquées techniquement dans cet environnement. La couverture complète demandée n’est donc pas atteinte.**

## Examen des 23 agences

« Restriction » signifie que la collecte récurrente et la republication prévues par cet agrégateur restent désactivées. Certains textes prévoient des exceptions d’usage privé ou de copie non substantielle ; elles ne sont pas assimilées à une licence générale pour un agrégateur déployable. Cela ne signifie pas que l’agence interdit toute consultation de ses offres ou ne dispose d’aucune API.

| Agence | Possibilité observée et résultat du test | État et préalable restant |
|---|---|---|
| Manpower | HTML public et routes de conditions dans les données de navigation Angular ; conditions intégrales lues. | Désactivée : extraction/reproduction/exploitation non expressément autorisées restreintes. [CGU](https://www.manpower.fr/contenu-statique/conditions-generales-d-utilisation). |
| Adecco | Migration `adecco.fr` → `adecco.com/fr-fr` vérifiée. Les conditions absentes du HTML visible ont été récupérées dans le JSON public `__NEXT_DATA__` de Next.js/Sitecore, sans connexion ni requête cachée. | Désactivée : reproduction/extraction/réutilisation du contenu expressément restreintes. Aucun endpoint d’offres activé. [Conditions](https://www.adecco.com/fr-fr/conditions-generales). |
| Adéquat | Site WordPress public ; conditions d’utilisation lues. Aucun flux d’offres confirmé. | Désactivée : reproduction réservée à l’information personnelle et privée ; autres usages soumis à autorisation. [Conditions](https://www.lejobadequat.com/mentions-legales). |
| Interaction | Liens d’offres individuels présents dans le HTML public ; mentions lues avant extraction. | Désactivée : reproduction/représentation pour usage personnel et privé, autorisation nécessaire pour étendre l’usage. [Mentions](https://www.interaction-interim.com/mentions-legales). |
| Crit | Site WordPress et liens RSS déclarés ; ces liens n’ont pas été validés comme flux d’offres. CGU intégrales lues. | Désactivée : reproduction/représentation du contenu soumis à autorisation expresse. [CGU](https://www.crit-job.com/conditions-generales-utilisation/). |
| Samsic | Site et page CGU accessibles. | Désactivée : **extraction automatisée, screen scraping et web scraping explicitement interdits sans accord de licence**, commercial ou non. [CGU](https://www.samsic-emploi.fr/cgu). |
| Proman | Site rendu par JavaScript. Le client public déclare GraphQL `/graphql`. GET a échoué (500) ; le POST de lecture utilisé par le client a répondu 200 pour `urlResolver` puis `cmsPage` des CGU, sans compte. Contenu des CGU décodé. | Désactivée : reproduction totale/partielle du contenu interdite. La lecture des CGU par API n’est **pas** une connexion aux offres. [CGU](https://www.proman-emploi.fr/cgu). |
| Advance Emploi | Tentatives sur les deux hôtes `advance-emploi.com` et `www.advance-emploi.com` ; CONNECT refusé par le proxy (403). | Bloquée par le réseau observé ; conditions, API, RSS et annonces non inspectables. L’échec ne prouve pas un blocage décidé par l’agence. |
| Partnaire | Offres individuelles dans le HTML, RSS WordPress déclaré ; conditions du compte personnel lues. | Désactivée par prudence pour la republication : clause interdisant réutilisation/modification/reproduction des éléments. Aucun accord de syndication établi. [CGU](https://www.partnaire.fr/conditions-generales-dutilisation/). |
| Mistertemp’ | Site public, lien vers `offres.mistertemp.com`, conditions lues. | Désactivée : extractions/réutilisations/copies sans autorisation explicitement interdites. Aucun accès candidat tenté. [Conditions](https://www.mistertemp.com/conditions-generales/). |
| Gojob | Site public, lien vers `app.gojob.com`, RSS WordPress déclaré ; CGU lues. | Désactivée : extraction pour activité similaire/concurrente ou recrutement restreinte ; aucun accord de réutilisation. [CGU](https://gojob.com/cgu-cgv/). |
| Randstad | Site public et sitemap déclarés ; mentions intégrales lues. | Désactivée : extraction/réutilisation substantielle de la base et conditions de reproduction restreintes. Un accord couvrant la collecte récurrente est nécessaire. [Mentions](https://www.randstad.fr/mentions-legales/). |
| Synergie | Offres individuelles visibles dans le HTML et sitemap ; mentions lues. | Désactivée : diffusion/reproduction à des fins autres que personnelles interdite. [Mentions](https://www.synergie.fr/mentions-legales). |
| Start People | Page d’offres publique identifiée ; mentions lues. | Désactivée : reproduction totale/partielle du site interdite sans autorisation expresse. [Mentions](https://www.startpeople.fr/mentions-legales). |
| R.A.S Intérim | Site et sitemap accessibles ; CGU lues. | Désactivée : représentation/reproduction/exploitation sans autorisation préalable écrite restreinte. [CGU](https://www.ras-interim.fr/cgu). |
| Temporis | Site public. Le lien de mentions avec slash redirige vers HTTP ; le même chemin canonique sans slash fonctionne en HTTPS et a permis de lire les mentions sans désactiver TLS. | Désactivée : extraction/réutilisation substantielle et copie collective restreintes. Les exceptions limitées ne couvrent pas automatiquement la collecte souhaitée. [Mentions](https://www.temporis-franchise.fr/mentions-legales). |
| Actual | Migration `groupeactual.eu` → `actualgroup.com` vérifiée par redirection officielle ; nouveau site et mentions accessibles. | Désactivée : extraction/réutilisation/exploitation sans autorisation écrite restreintes. [Mentions](https://www.actualgroup.com/mentions-legales). |
| **Triangle Intérim** | **API publique WordPress `/wp-json/wp/v2/job`, découverte dans l’index REST annoncé par le site. Recherche Toulon, vrais permaliens et champs structurés testés : 2 offres importées.** | **Activée, couverture partielle.** Le chemin AJAX `/wp-admin/admin-ajax.php` est interdit par robots et n’est jamais interrogé. Voir les limites ci-dessous. |
| Team Intérim | Site public et lien vers `recrutement.team-interim.fr` ; CGU du site lues. | Désactivée : extraction/réutilisation/reproduction publique restreintes. Aucun portail authentifié sollicité. [CGU](https://team-interim.fr/CGU/site-internet). |
| Staffmatch | Page publique d’offres identifiée ; mentions lues. | Désactivée : reproduction strictement personnelle et autres usages soumis à accord préalable. [Mentions](https://staffmatch.com/fr/legal/). |
| Intérim Nation | Site WordPress, pages d’offres et sitemap de jobs déclarés ; mentions lues. | Désactivée : reproduction/représentation sans autorisation expresse de Belvedia restreinte. [Mentions](https://interim-nation.fr/mentions-legales/). |
| Satis Jobs Center | Site public et mentions accessibles. | Désactivée : reproduction/publication/adaptation sans autorisation écrite préalable restreintes. [Mentions](https://satis-jobscenter.com/mentions-legales/). |
| R Intérim | `regional-interim.fr` : robots.txt répond 503. Aucun scraping d’offres effectué en l’absence de règles vérifiables. | Accès non validé. Une réponse valide du site ou un flux officiel reste nécessaire. Pas assimilée à Triangle simplement parce que les marques peuvent appartenir au même groupe. |

Les URLs des textes, extraits exacts et décisions sont enregistrés dans [source_reviews.json](source_reviews.json). La découverte et les résultats réseau figurent dans [agency_audit.json](agency_audit.json). [agency_network_audit.json](agency_network_audit.json) conserve le **premier** essai, lorsque le réseau bloquait encore les 23 domaines ; il ne décrit pas la situation finale.

## Limites de la connexion Triangle

- L’API WordPress ne couvre pas nécessairement les offres indexées dans le moteur complet. La page de recherche publique affichait dix cartes de Toulon, dont certaines issues d’un index externe ; l’API native n’a fourni que deux posts. Aucun chiffre de couverture globale n’est déduit de ces deux offres.
- Le scope testé est **Toulon**, pas toutes les communes du Var ni toutes les agences locales de Triangle. Les lieux sont confirmés par les attributs structurés du vrai permalink, pas par le mot recherché.
- La date enregistrée est la date de publication du post WordPress, nommée « publication sur le site ». Elle n’est pas assimilée à la date initiale de création de la mission dans un autre système. Les textes relatifs « il y a X jours » ne sont pas convertis en heures inventées.
- Les fiches donnent le contrat et le type de temps de travail ; les champs absents restent inconnus. La date de fin et l’employeur client ne sont pas exposés dans les données examinées et restent non précisés.
- Maximum trois pages API et trente fiches par collecte, délai minimal d’une seconde et respect des règles robots de chaque URL. Une limite de budget est visible comme collecte partielle ; une fiche dont la structure change provoque un diagnostic d’échec.
- L’index REST, les posts publiés et les permaliens sont accessibles publiquement ; aucun contournement du chemin AJAX interdit, authentification candidate ou accès à `my.triangle.fr` n’a lieu. Aucune interdiction spécifique d’extraction n’a été relevée dans [la page publique examinée](https://www.triangle.fr/politique-de-confidentialite/). Cela ne constitue pas une licence accordée par Triangle ; les conditions doivent être suivies et le connecteur suspendu si elles changent.

## Limites restantes de la version

Le RSS Emploi-Territorial est limité aux 100 éléments renvoyés lors du test ; ce n’est pas toutes les offres du département. La déduplication conservatrice peut conserver deux annonces équivalentes dont les descriptions ou les dates diffèrent. Elle évite de fusionner deux missions sur un titre seul.

L’historique, les versions et les contrôles sont persistés dans SQLite, mais le disque éphémère de Streamlit Community Cloud ne garantit pas leur conservation après redéploiement. Les exports CSV sont disponibles ; un volume persistant ou un stockage distant reste nécessaire pour une exploitation durable.

La couverture des 23 agences nécessite donc des flux de syndication/autorisations adaptés pour les 20 sources restreintes et la résolution des deux accès bloqués. Il n’existe dans cette livraison ni identifiant candidat, ni mot de passe, ni agence factice, ni redirection vers une recherche Google, ni source annoncée fonctionnelle sur la seule base d’un test synthétique.

## Validation et livraison

34 tests automatisés passent : normalisation, RSS, JSON-LD, API WordPress, robots, redirections, limites, erreurs réseau, historique, modifications, caches, filtres, déduplication et parcours Streamlit. Le JSON-LD est une capacité réutilisable testée sur fixtures ; aucune agence supplémentaire n’est déclarée connectée grâce à lui.

La validation réelle est reproductible avec `python scripts/verify_live.py`, distincte des tests synthétiques. La V5 est destinée à une branche dédiée et une pull request vers `main`. Les tests locaux ne constituent pas une validation sur l’infrastructure Streamlit Community Cloud ; vérifier les sources après mise en ligne selon [le guide de déploiement](DEPLOYMENT.md).

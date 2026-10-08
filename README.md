# JobRadar V5

Application Streamlit pour consulter des offres du Var, avec filtres, tri par date décroissante, provenance, déduplication, historique SQLite et diagnostic par source. Aucun compte candidat ni mot de passe. Les annonces sont affichées dans l’application et chaque lien mène à l’annonce originale.

**Couverture réellement vérifiée le 8 octobre 2026 : 1 agence sur 23, Triangle (2 offres de Toulon via les posts WordPress publics), plus Emploi-Territorial (100 offres du Var).** Le moteur complet de Triangle et les 22 autres agences ne sont pas connectés. Consultez le [bilan détaillé des 23 agences](docs/SOURCES.md), les [preuves des tests réels](docs/live_validation.json) et les [conditions examinées](docs/source_reviews.json). Ces nombres sont des observations datées, pas une garantie permanente.

## Installation et lancement

Python **3.12**. Les trois dépendances directes sont figées aux versions testées.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip check
.venv/bin/python -m streamlit run app.py
```

L’application collecte ses sources actives au démarrage puis, lors des interactions, au plus une fois par heure. Le bouton d’actualisation conserve une pause minimale d’une minute, et de 15 minutes après une erreur. Sans visite de l’application, aucun traitement de fond n’est lancé.

## Déploiement Streamlit Community Cloud

1. Dans Streamlit Community Cloud, créer une application depuis le dépôt `Mathieu-cmd83/Jobradar`. Pour essayer la V5 avant fusion, choisir la branche `codex/jobradar-v5` ; après fusion de la pull request, choisir `main`.
2. Choisir `app.py` comme fichier principal et Python 3.12 dans les paramètres avancés.
3. Laisser Streamlit installer `requirements.txt`. Aucun secret n’est requis pour les deux connecteurs actifs.
4. Vérifier dans **État des sources** une collecte réussie avec des annonces ; un serveur qui démarre ne suffit pas à valider les connecteurs.

Les dossiers `.data/`, `.venv/` et les secrets locaux sont ignorés par Git. La base est créée à l’exécution.

Voir les [instructions de mise en ligne et de vérification](docs/DEPLOYMENT.md), notamment pour une application déjà déployée.

## Stockage et disponibilité

Par défaut : `.data/jobradar.sqlite3`. La variable facultative `JOBRADAR_DB_PATH` permet de choisir un fichier SQLite sur un **volume persistant inscriptible**. SQLite utilise WAL et un délai de verrouillage de 30 secondes.

**Le disque local de Streamlit Community Cloud n’est pas un historique durable garanti.** Un redémarrage ou un redéploiement peut perdre les données. Les exports CSV disponibles dans les trois onglets conservent les offres filtrées, le diagnostic et les 300 dernières versions affichées. Pour un historique durable en production, héberger avec un volume persistant ou ajouter ultérieurement un stockage distant. Cette version ne prétend pas fournir ce dernier.

Les offres absentes d’un flux partiel restent enregistrées : absence ≠ retrait. Une échéance passée est déduite uniquement d’une date limite explicite. Sans date limite, la disponibilité reste à vérifier. Une dernière observation de plus de sept jours est signalée. Les erreurs d’une source préservent son historique et le dernier succès.

## Filtres et déduplication

Localisation, métier, mots-clés, titre seul/titre et description, temps plein/partiel/non précisé, contrat, sources, dates et affichage des échéances passées. Tri décroissant par instant de publication par défaut ; les dates inconnues restent à la fin et sont exclues des filtres de date. Les heures s’affichent à Paris ; « 24 dernières heures » est une fenêtre de 24 heures.

Les lieux structurés sont prioritaires. Une recherche textuelle de commune reste indicative si le lieu manque. Un poste public permanent n’est jamais automatiquement un CDI ; un titre de poste ne sert pas à inventer le contrat ou les horaires.

La déduplication utilise l’URL canonique, ou une correspondance stricte de titre, employeur, lieu structuré, date, contrat et description. Elle conserve toutes les provenances. Deux titres identiques ne suffisent pas à fusionner deux missions. Chaque observation et chaque modification sont conservées par source avant regroupement.

## Vérifications

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/verify_live.py
.venv/bin/python -m jobradar.cli status
```

Les tests unitaires et Streamlit utilisent des données synthétiques et des répertoires temporaires. **Ils ne prouvent pas l’accès réseau aux agences.** `verify_live.py` utilise une base temporaire neuve, effectue les vraies requêtes des connecteurs actifs, puis exécute l’application sans mocks avec ces annonces. Il retourne un échec si une source active n’importe pas d’offre ou si l’application échoue ; le résultat daté est enregistré dans `docs/live_validation.json`.

```bash
.venv/bin/python -m jobradar.cli audit --output docs/agency_audit.json
.venv/bin/python -m jobradar.cli sync --force
```

L’audit examine les chemins publics autorisés, les liens RSS, les sitemaps et les pages de conditions découvertes. Il **n’active jamais** une agence et ne prouve pas l’absence d’une API. Code de sortie 2 : au moins une agence reste bloquée ou nécessite un examen. La synchronisation utilise uniquement les sources activées dans `jobradar/registry.py`.

Les requêtes HTTPS gardent la vérification TLS, respectent `robots.txt`, les délais, les domaines déclarés et les redirections. Budget par source : 90 s, 50 requêtes, 4 Mio par réponse. Triangle : maximum 3 pages API et 30 fiches ; une limite atteinte est signalée comme collecte partielle. Les erreurs 401/403/429 et les formats modifiés ne sont pas contournés.

## Ajouter une agence

Le registre contient exactement les 23 enseignes retrouvées dans les anciennes versions Git. Un connecteur ne s’active qu’après examen des conditions, identification d’un endpoint d’offres public, test de ses vrais liens/données et vérification du filtrage géographique. Les parseurs RSS/Atom et JSON-LD `JobPosting` sont réutilisables ; le parseur JSON-LD est testé sur fixtures, mais aucune agence n’est présentée comme connectée par ce mécanisme.

Pour une agence soumise à autorisation, obtenir un flux de syndication ou un accord de réutilisation couvrant la collecte prévue. Les formulaires de candidature, comptes candidats, portails authentifiés, CAPTCHA et chemins interdits restent hors collecte. Ne pas activer un site sur la seule base d’un `robots.txt` permissif.

Pour planifier la collecte sur un hébergement avec disque persistant, lancer régulièrement `python -m jobradar.cli sync` avec le même `JOBRADAR_DB_PATH`. Aucun ordonnanceur n’est installé automatiquement.
# Suite de la V5

Voir [le bilan des corrections, dates et nouveaux contrôles de sources](docs/V6.md). Les audits V5 ci-dessous restent historiques ; aucune agence supplémentaire n’est annoncée connectée.

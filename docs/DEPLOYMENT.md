# Mettre JobRadar V5 en ligne

## Version et validation

La branche `codex/jobradar-v5` contient la V5 et cible `main` par pull request. Elle peut être déployée pour essai avant fusion. La fusion doit passer par GitHub ; aucune commande de déploiement ci-dessous ne pousse directement sur `main`.

Configuration testée : Python 3.12, dépendances de `requirements.txt`, `app.py` à la racine et tous les modules `jobradar/`. Les tests automatisés sont exécutés par GitHub Actions à chaque push et pull request. Les tests réseau réels restent séparés pour éviter de solliciter les sources à chaque build ; leurs résultats datés figurent dans `live_validation.json`.

## Nouvelle application sur Streamlit Community Cloud

1. Ouvrir <https://share.streamlit.io/> et se connecter avec le compte GitHub ayant accès au dépôt.
2. Créer une application depuis `Mathieu-cmd83/Jobradar`.
3. Choisir `codex/jobradar-v5` pour un essai avant fusion, ou `main` après fusion de la pull request.
4. Renseigner `app.py` comme fichier principal. Dans les paramètres avancés, choisir **Python 3.12**. Aucun secret ni identifiant candidat n’est nécessaire.
5. Déployer et attendre l’installation des dépendances. En cas d’échec, consulter les journaux dans la gestion de l’application.

Le fichier `.python-version` documente la version locale ; sélectionner explicitement Python dans l’interface Streamlit. Ne pas importer la base SQLite locale ni le dossier `.venv/` : la base est créée au lancement.

## Application existante

Si l’application suit déjà `main`, vérifier les contrôles de la pull request puis la fusionner dans GitHub. Streamlit redéploie normalement lors de la mise à jour de la branche suivie. Vérifier le fichier principal et Python 3.12 dans la configuration ; si le choix de version Python n’est plus modifiable, recréer l’application avec cette version. Consulter les journaux et utiliser le redémarrage depuis la gestion de l’application si nécessaire.

Pour essayer la V5 avant de toucher à l’application existante, créer une seconde application sur `codex/jobradar-v5`. La suppression ultérieure de cette branche affecterait cette application de test ; utiliser `main` pour l’application de production après fusion.

## Contrôles après mise en ligne

- Les onglets **Offres**, **État des sources** et **Historique** sont visibles sans erreur.
- Dans **État des sources**, Emploi-Territorial et Triangle affichent une collecte réussie et un dernier succès avec offres. Le nombre exact peut évoluer ; le test local daté a importé 100 + 2 offres.
- Les autres agences restent identifiées comme restreintes ou non connectées. **La V5 ne connecte pas les 23 agences : Triangle seule est vérifiée, avec une couverture partielle de Toulon.**
- Les filtres de lieu, métier, mots-clés, horaires, contrat et dates fonctionnent. Le tri par défaut place les dates les plus récentes en premier. Les liens ouvrent des annonces originales.
- Une panne réseau doit apparaître dans le suivi des sources ; ne pas assimiler le démarrage du serveur à une collecte validée. Le bouton d’actualisation respecte une pause d’une minute, et de 15 minutes après erreur.

## Historique et retour à la version précédente

Le disque local de Community Cloud peut être perdu après redémarrage, mise en veille ou redéploiement. Exporter les CSV avant une intervention si l’historique doit être conservé. Cette V5 n’intègre pas de base distante persistante. `JOBRADAR_DB_PATH` ne rend le stockage durable que sur un hébergement disposant réellement d’un volume persistant.

Avant fusion, l’application de test peut être arrêtée sans modifier `main`. Après fusion, un retour au code précédent se fait par une pull request de revert dans GitHub, puis redéploiement. Cela ne restaure pas une base SQLite perdue.

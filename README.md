# JobRadar — V1

Application Streamlit responsive pour agréger les annonces publiques. **La seule collecte implémentée est l’API officielle France Travail.** Les 23 autres enseignes figurent dans la configuration pour les intégrations futures ; elles ne sont pas collectées à ce stade.

## Lancer

1. Installer Python 3.10+.
2. `pip install -r requirements.txt`
3. Obtenir des identifiants pour l'API Offres d'emploi de France Travail via https://francetravail.io/ . Vérifier les scopes et droits accordés par France Travail.
4. Définir les variables d'environnement `FRANCE_TRAVAIL_CLIENT_ID` et `FRANCE_TRAVAIL_CLIENT_SECRET` (ne jamais les mettre dans un dépôt public).
5. `streamlit run app.py`

Le bouton **Actualiser maintenant** interroge réellement l’API. Les données et états de candidature sont conservés dans un fichier SQLite local (`jobradar.sqlite3`). Sur un hébergement éphémère, ils peuvent disparaître : utiliser un disque persistant ou une base distante pour un déploiement durable. Cette V1 ne propose ni comptes, ni synchronisation multi-appareils garantie, ni tâche planifiée. Pour un accès partagé, héberger l'application et prévoir une base persistante, une authentification et une séparation des données par utilisateur. Les requêtes peuvent être limitées par les quotas de l’API. Le champ département est initialisé à 83 et modifiable. Les filtres de rayon kilométrique et d'horaires restent à implémenter.

## État de réalisation

- Interface responsive, catégories, recherche texte, filtre de sources, suivi, favoris : implémentés.
- API France Travail : connecteur implémenté, **non testé avec des identifiants réels**.
- 23 autres sources : non connectées.
- Actualisation quotidienne : à déployer via planificateur externe.
- Comptes multi-utilisateurs : ultérieur.

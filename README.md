# JobRadar V3 — vrais flux d'annonces

Deux connecteurs publics sans clé ni compte candidat :
- Arbeitnow : https://www.arbeitnow.com/blog/job-board-api
- Remotive : https://remotive.com/remote-jobs/api

**Important** : ces flux ne remplacent pas une couverture locale de Toulon ou des agences d'intérim françaises. Arbeitnow est principalement européen/tech, Remotive exclusivement télétravail. Une recherche « Toulon » peut retourner zéro résultat. Aucune agence française ni France Travail n'est prétendue connectée.

## Déploiement Streamlit
Remplacer `app.py`, `requirements.txt`, `README.md` dans le dépôt GitHub existant. Streamlit Cloud se redéploie automatiquement. Aucun secret requis.

## Fonctionnement
- Appels HTTPS aux API publiques, 20 s de délai maximum par source.
- Cache 6 h pour éviter les requêtes répétées, bouton de rafraîchissement manuel.
- Filtres métier, mots-clés, localisation exacte, sources ; liens directs.
- Aucune donnée personnelle ou candidature conservée.
- Pas de tests réseau live dans l'environnement de construction ; vérifier l'accès aux flux depuis Streamlit Cloud après déploiement.

## Limites
- La couverture française et locale est faible ; la prochaine étape est l'intégration de sources françaises réellement autorisées.
- Les catégories sont des correspondances de mots-clés dans le titre, pas une classification sémantique.
- Pas de favoris durables ni de planification quotidienne.
- Les conditions des fournisseurs et les quotas doivent être respectés.

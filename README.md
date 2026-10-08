# JobRadar V2 — sans identifiants candidats

Application Streamlit de lancement de recherches ciblées sur des sites publics d'offres d'emploi.

## Installation

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Fonctionnement

- Choix d'un métier, de mots-clés, d'une zone et de sources.
- Chaque bouton ouvre une recherche Google limitée au domaine de la source concernée.
- **Aucun compte candidat, mot de passe, cookie de session ou clé API n'est demandé ou conservé par l'application.**
- **Ce n'est pas encore un agrégateur automatique** : aucune offre n'est importée, dédupliquée ou rafraîchie en arrière-plan.
- Les résultats de recherche externes peuvent être obsolètes, incomplets ou hors zone. Les domaines devront être revérifiés au fil du temps.
- Les recherches sont transmises à Google quand l'utilisateur clique ; les règles de confidentialité de Google s'appliquent.

## Déploiement Streamlit Cloud

Remplacer `app.py`, `README.md` et `requirements.txt` dans le dépôt GitHub, puis attendre le redéploiement. Aucun secret Streamlit requis.

## Suite du projet

Tester un à un des connecteurs autorisés, intégrer de vraies offres et leur date, puis prévoir un stockage privé et durable des favoris avant de rétablir le suivi de candidatures.

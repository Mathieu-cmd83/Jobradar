# JobRadar V4

Application Streamlit : récupération des offres du Var à partir du flux RSS public **Emploi-Territorial**.

Source : https://www.emploi-territorial.fr/rss?search-dept=083

- Aucune clé API et aucun compte candidat.
- Actualisation à la demande et cache d'une heure.
- Filtres métier, mots-clés, zone approximative autour de Toulon.
- Aucun suivi partagé des candidatures.

## Installation

Remplacer `app.py`, `requirements.txt` et `README.md` dans le dépôt GitHub, puis valider le commit. Streamlit Community Cloud redéploiera normalement automatiquement.

## Limites

Cette V4 n'est **pas** encore un agrégateur des agences d'intérim : elle ne couvre que les offres de collectivités territoriales du Var présentes dans le flux. Le contenu exact et la quantité d'annonces ne peuvent être garantis. Le flux RSS peut renvoyer une erreur ou une liste partielle. Le filtrage géographique s'appuie sur les mots présents dans le texte du flux ; certaines offres locales peuvent ne pas être reconnues. Les conditions de réutilisation du flux doivent être respectées.

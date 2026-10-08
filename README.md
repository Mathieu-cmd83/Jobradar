# JobRadar V4.2

## Installation
Remplacer `app.py`, `requirements.txt` et `README.md` dans le dépôt GitHub relié à Streamlit Cloud.

## Nouveaux filtres
- Temps de travail : indifférent, temps plein uniquement, temps partiel uniquement, non précisé.
- Type de contrat / emploi : sélection multiple (CDI, CDD, intérim, emploi permanent/ temporaire public, contrat de projet, alternance, stage, autre, non précisé).
- Tous les filtres de la V4.1 sont conservés, notamment le **tri décroissant par date de parution par défaut**.

## Important
La seule source connectée reste le RSS Emploi-Territorial Var : https://www.emploi-territorial.fr/rss?search-dept=083 . Le flux ne garantit pas la présence des informations « type de contrat » et « temps de travail » : JobRadar n'invente pas les données manquantes. Les emplois permanents de la fonction publique ne sont **pas** classés automatiquement en CDI. Un filtre strict écarte les offres dont le champ n'est pas précisé. Pas d'identifiant candidat ni de clé API.

"""JobRadar V2: public job-search launcher, no candidate credentials."""
from urllib.parse import urlencode
import streamlit as st

st.set_page_config(page_title="JobRadar", page_icon="📡", layout="wide")

CATEGORIES = {
    "Logistique / magasinage": "préparateur commandes magasinier cariste",
    "Livraison VL": "chauffeur livreur VL",
    "Manutention / industrie": "manutentionnaire opérateur production",
    "Maintenance / technique": "technicien maintenance",
    "BTP / chantier": "ouvrier chantier préparateur travaux",
    "Bureau d’études": "dessinateur projeteur métreur économiste construction",
    "Accueil / restauration": "accueil serveur restauration",
}
# Domains are search scopes, NOT connected feeds. Verify individual search results at source.
SITES = {
    "France Travail": "francetravail.fr",
    "Manpower": "manpower.fr", "Adecco": "adecco.fr", "Adéquat": "lejobadequat.com",
    "Interaction": "interaction-interim.com", "Crit": "crit-job.com",
    "Samsic": "samsic-emploi.fr", "Proman": "proman-emploi.fr",
    "Advance Emploi": "advance-emploi.com", "Partnaire": "partnaire.fr",
    "Mistertemp'": "mistertemp.com", "Gojob": "gojob.com",
    "Randstad": "randstad.fr", "Synergie": "synergie.fr",
    "Start People": "startpeople.fr", "R.A.S Intérim": "ras-interim.fr",
    "Temporis": "temporis-franchise.fr", "Actual": "groupeactual.eu",
    "Triangle Intérim": "triangle.fr", "Team Intérim": "team-interim.fr",
    "Staffmatch": "staffmatch.com", "Intérim Nation": "interim-nation.fr",
    "Satis Jobs Center": "satis-jobscenter.com", "R Intérim": "regional-interim.fr",
}

st.title("📡 JobRadar")
st.caption("V2 · Recherche sur des sites publics · Aucun compte candidat, aucune clé API")
st.info("Cette version ouvre des recherches web ciblées sur les sites des recruteurs. Elle ne collecte pas encore les annonces automatiquement. Les résultats externes doivent être vérifiés sur le site d'origine.")
with st.sidebar:
    st.header("Recherche")
    category = st.selectbox("Métier", ["Tous les métiers"] + list(CATEGORIES))
    keyword = st.text_input("Mots-clés supplémentaires", placeholder="Ex. préparateur de commandes")
    city = st.text_input("Ville / zone", value="Toulon Var")
    selected = st.multiselect("Sources à afficher", list(SITES), default=list(SITES))
    st.caption("Les sites ci-dessous ne sont pas encore des connecteurs automatiques.")

terms = keyword.strip() or (CATEGORIES[category] if category != "Tous les métiers" else "emploi")
st.write(f"**Recherche :** {terms} · **Zone :** {city}")
if not selected:
    st.warning("Sélectionne au moins une source dans la barre latérale.")
else:
    st.metric("Sites de recherche sélectionnés", len(selected))
    for name in selected:
        domain = SITES[name]
        q = f'site:{domain} "{city.strip()}" {terms} emploi'
        url = "https://www.google.com/search?" + urlencode({"q": q})
        with st.container(border=True):
            left, right = st.columns([3, 1])
            left.markdown(f"**{name}**")
            left.caption(f"Recherche externe ciblée sur {domain} · aucune offre importée")
            right.link_button("Voir les offres ↗", url, use_container_width=True)

st.divider()
st.caption("Confidentialité : JobRadar ne reçoit ni mot de passe candidat ni données de candidature. Les recherches sont ouvertes dans Google ; ses propres règles de confidentialité s'appliquent. Les résultats peuvent être anciens ou incomplets.")

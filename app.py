"""JobRadar V4 — public Var territorial RSS, no candidate accounts."""
import re
from datetime import datetime, timezone
from urllib.parse import urlparse
import requests
import feedparser
import streamlit as st

st.set_page_config(page_title='JobRadar V4', page_icon='📡', layout='wide')
RSS_URL = 'https://www.emploi-territorial.fr/rss?search-dept=083'
CATEGORIES = {
    'Tous les métiers': [],
    'Logistique / magasinage': ['logist', 'magasin', 'stock', 'approvision', 'cariste'],
    'Livraison VL': ['livreur', 'livraison', 'chauffeur', 'conducteur'],
    'Manutention / industrie': ['manutention', 'production', 'ouvrier', 'atelier', 'polyvalent'],
    'Maintenance / technique': ['maintenance', 'technicien', 'mécanicien', 'electricien', 'électricien', 'agent technique'],
    'BTP / chantier': ['chantier', 'travaux', 'bâtiment', 'batiment', 'maçon', 'voirie', 'construction'],
    'Bureau d’études': ['études', 'etudes', 'dessinateur', 'projeteur', 'métreur', 'économiste', 'urbanisme', 'ingénieur'],
    'Accueil / restauration': ['accueil', 'restauration', 'cuisine', 'serveur', 'agent de service'],
}
NEAR = ['toulon', 'la seyne', 'six-fours', 'la garde', 'la valette', 'la farlède', 'la farlede', 'le pradet', 'carqueiranne', 'ollioules', 'la crau', 'hyères', 'hyeres', 'solliès', 'sollies', 'le revest', 'cuers', 'saint-mandrier', 'bandol', 'sanary']

def valid_link(value):
    p = urlparse(str(value or ''))
    return p.scheme == 'https' and p.hostname in ('www.emploi-territorial.fr', 'emploi-territorial.fr')

def parse_rss(data):
    parsed = feedparser.parse(data)
    if parsed.bozo and not parsed.entries:
        raise ValueError('Le flux RSS est illisible')
    out = []
    for entry in parsed.entries:
        title = re.sub(r'<[^>]*>', '', str(entry.get('title', ''))).strip()
        link = entry.get('link', '')
        if not title or not valid_link(link):
            continue
        description = re.sub(r'<[^>]*>', ' ', str(entry.get('summary', '')))
        description = re.sub(r'\s+', ' ', description).strip()
        date = str(entry.get('published', entry.get('updated', '')))
        if entry.get('published_parsed'):
            date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).strftime('%Y-%m-%d')
        out.append({'title': title, 'url': link, 'description': description[:450], 'date': date, 'source': 'Emploi-Territorial (Var)'})
    return out

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_jobs():
    response = requests.get(RSS_URL, timeout=25, headers={'User-Agent': 'JobRadar/4.0 (+public RSS reader)', 'Accept': 'application/rss+xml, application/xml, text/xml'})
    response.raise_for_status()
    jobs = parse_rss(response.content)
    return jobs

st.title('📡 JobRadar')
st.caption('V4 · Annonces publiques du Var · Sans compte candidat ni clé API')
st.info('Source française connectée : flux RSS Emploi-Territorial (offres des collectivités du Var). Les agences d’intérim ne sont pas encore connectées.')
with st.sidebar:
    st.header('Recherche')
    category = st.selectbox('Métier', list(CATEGORIES))
    words = st.text_input('Mots-clés', placeholder='Ex. magasinier, travaux')
    area = st.selectbox('Zone', ['Tout le Var', 'Autour de Toulon'])
    if st.button('🔄 Actualiser les annonces', use_container_width=True):
        fetch_jobs.clear()

try:
    jobs = fetch_jobs()
except (requests.RequestException, ValueError) as exc:
    st.error('Impossible de lire le flux territorial : ' + str(exc)[:180])
    st.markdown('[Voir les offres du Var sur le site officiel](https://www.emploi-territorial.fr/emploi-mobilite/?search-dept=083)')
    st.stop()

st.caption(f'{len(jobs)} annonces reçues du flux RSS · actualisation en cache 1 heure')
terms = [x.casefold() for x in words.split() if x.strip()]
filtered = []
for job in jobs:
    text = (job['title'] + ' ' + job['description']).casefold()
    if CATEGORIES[category] and not any(x in text for x in CATEGORIES[category]):
        continue
    if terms and not all(x in text for x in terms):
        continue
    if area == 'Autour de Toulon' and not any(x in text for x in NEAR):
        continue
    filtered.append(job)
st.metric('Offres correspondant aux filtres', len(filtered))
if not filtered:
    st.warning('Aucune offre dans le flux pour ces filtres. Essaie « Tout le Var » et « Tous les métiers ». Le flux peut aussi ne présenter qu’une partie des offres du site.')
for job in filtered[:200]:
    with st.container(border=True):
        st.subheader(job['title'])
        st.caption('📍 Var · ' + job['source'] + (' · ' + job['date'] if job['date'] else ''))
        if job['description']:
            st.write(job['description'])
        st.link_button('Voir l’annonce originale ↗', job['url'])
st.caption('JobRadar ne collecte aucun identifiant candidat et ne stocke aucune candidature. Les informations de localisation proviennent du texte du flux : le filtre autour de Toulon est indicatif.')

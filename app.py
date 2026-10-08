"""JobRadar V4.2 — annonces du Var via flux RSS public Emploi-Territorial."""
import re
import unicodedata
from datetime import datetime, date, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import feedparser
import requests
import streamlit as st

st.set_page_config(page_title='JobRadar V4.2', page_icon='📡', layout='wide')
RSS_URL = 'https://www.emploi-territorial.fr/rss?search-dept=083'
CATEGORIES = {
    'Tous les métiers': [],
    'Logistique / magasinage': ['logist', 'magasin', 'stock', 'approvision', 'cariste'],
    'Livraison VL': ['livreur', 'livraison', 'chauffeur', 'conducteur'],
    'Manutention / industrie': ['manutention', 'production', 'ouvrier', 'atelier', 'polyvalent'],
    'Maintenance / technique': ['maintenance', 'technicien', 'mecanicien', 'electricien', 'agent technique'],
    'BTP / chantier': ['chantier', 'travaux', 'batiment', 'macon', 'voirie', 'construction'],
    'Bureau d’études': ['etudes', 'dessinateur', 'projeteur', 'metreur', 'economiste', 'urbanisme', 'ingenieur'],
    'Accueil / restauration': ['accueil', 'restauration', 'cuisine', 'serveur', 'agent de service'],
}
NEAR = ['toulon', 'la seyne', 'six fours', 'la garde', 'la valette', 'la farlede', 'le pradet', 'carqueiranne', 'ollioules', 'la crau', 'hyeres', 'sollies', 'le revest', 'cuers', 'saint mandrier', 'bandol', 'sanary']


def normalize(s):
    s = unicodedata.normalize('NFKD', str(s or '').casefold())
    return re.sub(r'\s+', ' ', ''.join(c for c in s if not unicodedata.combining(c)).replace('-', ' ')).strip()


def valid_link(value):
    p = urlparse(str(value or ''))
    return p.scheme == 'https' and p.hostname in ('www.emploi-territorial.fr', 'emploi-territorial.fr')


def entry_date(entry):
    """Published preferred; updated only as fallback. Unknown date stays None."""
    for field in ('published_parsed', 'updated_parsed'):
        value = entry.get(field)
        if value:
            try:
                return date(*value[:3]), 'publication' if field == 'published_parsed' else 'mise à jour'
            except (TypeError, ValueError):
                pass
    for field in ('published', 'updated'):
        raw = entry.get(field)
        if not raw:
            continue
        try:
            return parsedate_to_datetime(raw).date(), 'publication' if field == 'published' else 'mise à jour'
        except (ValueError, TypeError, IndexError):
            try:
                return date.fromisoformat(str(raw)[:10]), 'publication' if field == 'published' else 'mise à jour'
            except ValueError:
                pass
    return None, None


CONTRACT_OPTIONS = ['CDI', 'CDD', 'Intérim', 'Emploi permanent (fonction publique)',
                    'Emploi temporaire (fonction publique)', 'Contrat de projet',
                    'Apprentissage / alternance', 'Stage', 'Autre', 'Non précisé']


def extract_employment_details(description):
    """Ne jamais deviner un contrat ou un temps plein à partir du titre.

    Les catégories de la fonction publique ne sont pas des CDI/CDD de droit privé.
    """
    text = normalize(description)
    # La donnée doit figurer explicitement dans la fiche ou dans le flux.
    full_time = None
    if re.search(r'\btemps\s+non\s+complet\b|\btemps\s+partiel\b', text):
        full_time = False
    elif re.search(r'\btemps\s+complet\b|\btemps\s+plein\b', text):
        full_time = True

    contract = 'Non précisé'
    patterns = [
        (r'\bcontrat\s+de\s+projet\b', 'Contrat de projet'),
        (r'\bemploi\s+temporaire\b', 'Emploi temporaire (fonction publique)'),
        (r'\bemploi\s+permanent\b', 'Emploi permanent (fonction publique)'),
        (r'\binterim\b|\bmission\s+d.interim\b', 'Intérim'),
        (r'\bcontrat\s+d.apprentissage\b|\balternance\b', 'Apprentissage / alternance'),
        (r'\bstage\b|\bstagiaire\b', 'Stage'),
        (r'\bcontrat\s+a\s+duree\s+indeterminee\b|\bcdi\b', 'CDI'),
        (r'\bcontrat\s+a\s+duree\s+determinee\b|\bcdd\b', 'CDD'),
    ]
    for pattern, label in patterns:
        if re.search(pattern, text):
            contract = label
            break
    return full_time, contract


def parse_rss(data):
    parsed = feedparser.parse(data)
    if parsed.bozo and not parsed.entries:
        raise ValueError('Le flux RSS est illisible')
    out, seen = [], set()
    for entry in parsed.entries:
        title = re.sub(r'<[^>]*>', '', str(entry.get('title', ''))).strip()
        link = entry.get('link', '')
        if not title or not valid_link(link) or link in seen:
            continue
        seen.add(link)
        description = re.sub(r'<[^>]*>', ' ', str(entry.get('summary', '')))
        description = re.sub(r'\s+', ' ', description).strip()
        published, date_kind = entry_date(entry)
        full_time, contract = extract_employment_details(description)
        out.append({'title': title, 'url': link, 'description': description[:1500], 'date': published,
                    'date_kind': date_kind, 'full_time': full_time, 'contract': contract, 'source': 'Emploi-Territorial (Var)'})
    return out


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_jobs():
    response = requests.get(RSS_URL, timeout=25, headers={
        'User-Agent': 'JobRadar/4.2 (public RSS reader)',
        'Accept': 'application/rss+xml, application/xml, text/xml'})
    response.raise_for_status()
    return parse_rss(response.content)


st.title('📡 JobRadar')
st.caption('V4.2 · Offres publiques du Var · Sans compte candidat ni clé API')
st.info('Source connectée : Emploi-Territorial (collectivités du Var). Les agences d’intérim ne sont pas encore connectées.')

with st.sidebar:
    st.header('Filtres de recherche')
    category = st.selectbox('Métier', list(CATEGORIES))
    words = st.text_input('Mots-clés', placeholder='Ex. magasinier, travaux')
    search_scope = st.selectbox('Rechercher dans', ['Titre et description', 'Titre uniquement'])
    area = st.selectbox('Zone', ['Tout le Var', 'Autour de Toulon (indicatif)', 'Commune / lieu à préciser'])
    location = st.text_input('Commune ou lieu', placeholder='Ex. Toulon, La Garde') if area == 'Commune / lieu à préciser' else ''
    hours = st.selectbox('Temps de travail', ['Indifférent', 'Temps plein uniquement', 'Temps partiel uniquement', 'Non précisé'])
    contracts = st.multiselect('Type de contrat / emploi', CONTRACT_OPTIONS, placeholder='Tous les types')
    st.caption('Les offres sans indication explicite restent « Non précisé ». Dans la fonction publique, « emploi permanent » ne signifie pas nécessairement CDI.')
    period = st.selectbox('Date de parution', ['Toutes les dates', '24 dernières heures', '3 derniers jours', '7 derniers jours', '14 derniers jours', '30 derniers jours', 'Période personnalisée'])
    start, end = None, None
    today = datetime.now(timezone.utc).date()
    days = {'24 dernières heures': 1, '3 derniers jours': 3, '7 derniers jours': 7,
            '14 derniers jours': 14, '30 derniers jours': 30}
    if period in days:
        start = today - timedelta(days=days[period])
        end = today
    elif period == 'Période personnalisée':
        start = st.date_input('Du', value=today - timedelta(days=7), max_value=today)
        end = st.date_input('Au', value=today, max_value=today)
    sort = st.selectbox('Trier les résultats', ['Plus récentes d’abord', 'Plus anciennes d’abord', 'Titre A → Z'])
    max_results = st.selectbox('Annonces affichées', [25, 50, 100, 200], index=1)
    if st.button('🔄 Actualiser les annonces', use_container_width=True):
        fetch_jobs.clear()
        st.rerun()

try:
    jobs = fetch_jobs()
except (requests.RequestException, ValueError) as exc:
    st.error('Impossible de lire le flux territorial : ' + str(exc)[:180])
    st.markdown('[Consulter les offres du Var sur le site officiel](https://www.emploi-territorial.fr/emploi-mobilite/?search-dept=083)')
    st.stop()

st.caption(f'{len(jobs)} annonces reçues du flux RSS · cache d’une heure · la date affichée vient du flux')
if start and end and start > end:
    st.error('La date de début doit être antérieure ou égale à la date de fin.')
    st.stop()

terms = [normalize(x) for x in words.split() if x.strip()]
filtered = []
unknown_dates = 0
for job in jobs:
    full_text = normalize(job['title'] + ' ' + job['description'])
    searched_text = normalize(job['title']) if search_scope == 'Titre uniquement' else full_text
    if CATEGORIES[category] and not any(x in searched_text for x in CATEGORIES[category]):
        continue
    if terms and not all(x in searched_text for x in terms):
        continue
    if area == 'Autour de Toulon (indicatif)' and not any(x in full_text for x in NEAR):
        continue
    if location and normalize(location) not in full_text:
        continue
    if hours == 'Temps plein uniquement' and job['full_time'] is not True:
        continue
    if hours == 'Temps partiel uniquement' and job['full_time'] is not False:
        continue
    if hours == 'Non précisé' and job['full_time'] is not None:
        continue
    if contracts and job['contract'] not in contracts:
        continue
    if start is not None:
        if job['date'] is None:
            unknown_dates += 1
            continue
        if not (start <= job['date'] <= end):
            continue
    filtered.append(job)

if sort == 'Plus récentes d’abord':
    filtered.sort(key=lambda j: (j['date'] is not None, j['date'] or date.min), reverse=True)
elif sort == 'Plus anciennes d’abord':
    filtered.sort(key=lambda j: (j['date'] is None, j['date'] or date.max))
else:
    filtered.sort(key=lambda j: normalize(j['title']))

st.metric('Offres correspondant aux filtres', len(filtered))
if start is not None:
    st.caption(f'Période : {start.strftime("%d/%m/%Y")} au {end.strftime("%d/%m/%Y")} (dates calendaires).')
    if unknown_dates:
        st.warning(f'{unknown_dates} offre(s) sans date exploitable écartée(s) par le filtre de date.')
if not filtered:
    st.warning('Aucune offre dans le flux pour ces filtres. Essaie « Tout le Var », « Toutes les dates » et « Tous les métiers ». Le flux peut ne présenter qu’une partie des offres du site.')
for job in filtered[:max_results]:
    with st.container(border=True):
        st.subheader(job['title'])
        shown_date = job['date'].strftime('%d/%m/%Y') if job['date'] else 'Date non renseignée'
        date_label = f'{job["date_kind"].capitalize()} : {shown_date}' if job['date_kind'] else shown_date
        work_time = 'Temps plein' if job['full_time'] is True else ('Temps partiel' if job['full_time'] is False else 'Temps non précisé')
        st.caption(f'📍 Var (localisation détaillée non structurée) · {job["source"]} · {date_label}')
        st.caption(f'🕒 {work_time} · 📄 {job["contract"]}')
        if job['description']:
            st.write(job['description'])
        st.link_button('Voir l’annonce originale ↗', job['url'])
if len(filtered) > max_results:
    st.caption(f'{max_results} offres affichées sur {len(filtered)}. Augmente « Annonces affichées » dans les filtres.')
st.caption('Attention : les filtres de zone cherchent des noms de communes dans le titre et la description, pas dans un champ géographique certifié. Une annonce peut être exclue si sa commune ne figure pas dans le flux. « Date de parution » utilise la date de publication RSS, ou la date de mise à jour si la publication est absente. La recherche « 24 dernières heures » est calculée par dates calendaires.')

st.caption('Les types de contrat et temps de travail sont identifiés uniquement lorsqu’ils sont mentionnés explicitement dans le texte du flux RSS ; les informations absentes restent non précisées. Un filtre strict peut donc masquer des offres pertinentes.')

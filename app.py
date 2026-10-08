"""JobRadar V5 — offres intégrées, provenance, historique et suivi par source."""
import csv
from datetime import datetime, timedelta
import io
import json
import os
from pathlib import Path
import sqlite3

import streamlit as st

from jobradar.models import CONTRACT_OPTIONS, PARIS, UTC
from jobradar.registry import SOURCES
from jobradar.service import deduplicate, filter_jobs, refresh
from jobradar.storage import Store

ROOT = Path(__file__).resolve().parent
st.set_page_config(page_title='JobRadar', page_icon='📡', layout='wide')
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
STATUS_LABELS = {
    'ok': 'Collecte réussie', 'empty': 'Collecte réussie, aucune offre du Var',
    'network_blocked': 'Bloquée par le réseau cloud', 'network_error': 'Source inaccessible',
    'robots_denied': 'Collecte interdite par robots.txt', 'access_blocked': 'Accès bloqué',
    'rate_limited': 'Limite de requêtes atteinte', 'http_error': 'Erreur HTTP',
    'format_error': 'Format non exploitable', 'review_pending': 'Conditions et endpoint à vérifier',
    'not_connected': 'Non connectée',
    'terms_restricted': 'Réutilisation soumise à autorisation',
    'connector_implemented': 'Connecteur implémenté — test de collecte à consulter',
    'partial': 'Collecte partielle', 'budget_exceeded': 'Budget de collecte atteint',
}


def date_label(value):
    return datetime.fromisoformat(value).astimezone(PARIS).strftime('%d/%m/%Y %H:%M') if value else 'Non renseignée'


def as_csv(rows):
    def cell(value):
        text = str(value if value is not None else '')
        return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) else text
    buffer = io.StringIO()
    keys = list(dict.fromkeys(key for row in rows for key in row))
    writer = csv.DictWriter(buffer, fieldnames=keys)
    writer.writeheader()
    for row in rows:
        writer.writerow({key: cell(value) for key, value in row.items()})
    return ('\ufeff' + buffer.getvalue()).encode('utf-8')


try:
    store = Store(os.environ.get('JOBRADAR_DB_PATH', str(ROOT / '.data' / 'jobradar.sqlite3')))
except (OSError, sqlite3.Error):
    st.error('Le stockage des annonces est inaccessible. Configurez JOBRADAR_DB_PATH vers un répertoire inscriptible.')
    st.stop()

st.title('📡 JobRadar')
st.caption('Offres du Var et de Toulon · Aucun compte candidat · Provenance et état des sources visibles')

with st.sidebar:
    st.header('Filtres de recherche')
    category = st.selectbox('Métier', list(CATEGORIES))
    words = st.text_input('Mots-clés', placeholder='Ex. magasinier, travaux')
    scope = st.selectbox('Rechercher dans', ['Titre et description', 'Titre uniquement'])
    area = st.selectbox('Zone', ['Tout le Var', 'Autour de Toulon (indicatif)', 'Commune / lieu à préciser'])
    location = st.text_input('Commune ou lieu', placeholder='Ex. Toulon, La Garde') if area == 'Commune / lieu à préciser' else ''
    hours = st.selectbox('Temps de travail', ['Indifférent', 'Temps plein uniquement', 'Temps partiel uniquement', 'Non précisé'])
    contracts = st.multiselect('Type de contrat / emploi', CONTRACT_OPTIONS, placeholder='Tous les types')
    names = {s.id: s.name for s in SOURCES}
    selected = st.multiselect('Sources', list(names), default=list(names), format_func=names.get)
    period = st.selectbox('Date de parution', ['Toutes les dates', '24 dernières heures', '3 derniers jours',
                                            '7 derniers jours', '14 derniers jours', '30 derniers jours', 'Période personnalisée'])
    now = datetime.now(UTC)
    today = now.astimezone(PARIS).date()
    start, end, since = None, None, None
    if period == '24 dernières heures':
        since = now - timedelta(hours=24)
    elif period in ('3 derniers jours', '7 derniers jours', '14 derniers jours', '30 derniers jours'):
        start, end = today - timedelta(days=int(period.split()[0]) - 1), today
    elif period == 'Période personnalisée':
        start = st.date_input('Du', value=today - timedelta(days=7), max_value=today)
        end = st.date_input('Au', value=today, max_value=today)
    sort = st.selectbox('Trier les résultats', ['Plus récentes d’abord', 'Plus anciennes d’abord', 'Titre A → Z'])
    max_results = st.selectbox('Annonces affichées', [25, 50, 100, 200], index=1)
    include_expired = st.checkbox('Inclure les annonces à échéance passée')
    force = st.button('🔄 Actualiser les annonces', width='stretch')
    st.caption('Actualisation automatique au plus une fois par heure ; pause de 15 min après une erreur. '
               'Les champs absents restent non précisés. Emploi public permanent ≠ CDI.')

try:
    refresh(SOURCES, store, force=force)
    states = store.states()
except (OSError, sqlite3.Error):
    st.error('Le stockage ne permet pas la collecte. Vérifiez JOBRADAR_DB_PATH et les droits du répertoire.')
    st.stop()
audit_path = ROOT / 'docs' / 'agency_audit.json'
try:
    audits = {r['source_id']: r for r in json.loads(audit_path.read_text(encoding='utf-8'))['agencies']}
except (OSError, ValueError, KeyError):
    audits = {}

source_rows = []
for source in SOURCES:
    state = states.get(source.id, {})
    audit = audits.get(source.id, {})
    status = state.get('status', audit.get('status', 'not_connected'))
    if not source.enabled and state:
        status = audit.get('status', 'not_connected')
    source_rows.append({
        'Source': source.name, 'Collecte activée': 'Oui' if source.enabled else 'Non',
        'Conditions': 'Réutilisation restreinte' if source.access_review == 'restricted' else 'Examinées' if source.access_review in ('approved', 'public_rss') else 'À examiner',
        'Page examinée': source.terms_url,
        'État': STATUS_LABELS.get(status, status),
        'Dernier contrôle': date_label(state.get('checked_at') if source.enabled else audit.get('checked_at')),
        'Dernier succès avec offres': date_label(state.get('last_nonempty_success')),
        'Offres reçues': state.get('fetched', 0), 'Offres du Var importées': state.get('imported', 0),
        'Détail': state.get('message', '') if source.enabled else audit.get('message', 'Endpoint et conditions non examinés.'),
    })

agency_ids = {s.id for s in SOURCES if s.id != 'territorial'}
verified_agencies = sum(1 for s in SOURCES if s.id in agency_ids and s.enabled
                        and states.get(s.id, {}).get('status') in ('ok', 'partial')
                        and states[s.id].get('last_nonempty_success'))
st.info(f'{verified_agencies}/23 agences d’intérim avec une collecte vérifiée. '
        'Le suivi distingue les collectes réussies des annonces conservées en historique.')
for source in SOURCES:
    state = states.get(source.id, {})
    if source.enabled and state.get('status') not in ('ok', 'empty'):
        st.warning(f"{source.name} : {state.get('message', 'Pas de collecte réussie.')} "
                   'Les annonces déjà enregistrées restent consultables avec leur date de dernière observation.')

offers_tab, sources_tab, history_tab = st.tabs(['Offres', 'État des sources', 'Historique'])
with offers_tab:
    jobs = deduplicate(store.jobs())
    if start and end and start > end:
        st.error('La date de début doit être antérieure ou égale à la date de fin.')
        filtered, unknown = [], 0
    else:
        filtered, unknown = filter_jobs(
            jobs, selected_sources=set(selected), keywords=words, title_only=scope == 'Titre uniquement',
            category_terms=CATEGORIES[category], zone='near' if area.startswith('Autour') else 'var',
            location=location, hours={'Indifférent': 'any', 'Temps plein uniquement': 'full',
                                      'Temps partiel uniquement': 'part', 'Non précisé': 'unknown'}[hours],
            contracts=contracts, start=start, end=end, since=since, include_expired=include_expired,
            now=now, sort={'Plus récentes d’abord': 'recent', 'Plus anciennes d’abord': 'oldest', 'Titre A → Z': 'title'}[sort])
    st.metric('Offres correspondant aux filtres', len(filtered))
    st.caption(f'{len(jobs)} annonces distinctes dans l’historique local. Les sources peuvent publier des listes partielles. '
               'Une annonce absente du dernier flux reste conservée ; son absence ne prouve pas son retrait.')
    if unknown:
        st.caption(f'{unknown} annonce(s) sans date exploitable exclue(s) par le filtre de date.')
    if not filtered:
        st.warning('Aucune offre pour ces filtres. Consultez l’état des sources et les annonces à échéance passée.')
    for job in filtered[:max_results]:
        with st.container(border=True):
            st.subheader(job['title'])
            st.caption(f"📍 {job['location'] or 'Var — lieu non précisé'} · {job['employer'] or 'Employeur non précisé'}")
            kind = job.get('date_kind') or 'date'
            st.caption(f"{kind.capitalize()} : {date_label(job.get('published_at'))} · "
                       f"Dernière observation : {date_label(job['last_seen'])}")
            work_time = 'Temps plein' if job.get('full_time') is True else 'Temps partiel' if job.get('full_time') is False else 'Temps non précisé'
            st.caption(f"🕒 {work_time} · 📄 {job.get('contract', 'Non précisé')}")
            if job['expired']:
                st.warning('Échéance de candidature passée selon la source.')
            if job['stale']:
                st.caption('Annonce non revue depuis plus de sept jours : disponibilité à vérifier.')
            if job.get('description'):
                st.write(job['description'])
            for origin in job['origins']:
                st.link_button(f"Voir l’annonce originale · {origin['source_name']} ↗", origin['url'])
    if len(filtered) > max_results:
        st.caption(f'{max_results} offres affichées sur {len(filtered)}.')
    if filtered:
        export = [{k: j.get(k) for k in ('title', 'employer', 'location', 'contract', 'full_time', 'published_at',
                                         'expires_at', 'url', 'first_seen', 'last_seen')}
                  | {'sources': ', '.join(o['source_name'] for o in j['origins'])} for j in filtered]
        st.download_button('Exporter les offres filtrées (CSV)', as_csv(export), 'jobradar-offres.csv', 'text/csv')
    st.caption('Les lieux structurés sont utilisés en priorité ; les recherches dans le texte sont indicatives lorsque le lieu manque. '
               'Les dates sont affichées à l’heure de Paris. Un flux indiquant seulement le jour ne permet pas de connaître l’heure exacte de parution.')

with sources_tab:
    st.dataframe(source_rows, hide_index=True, width='stretch')
    st.caption('Un accès réseau ou une page d’accueil lisible ne suffit pas à valider un connecteur. '
               'Aucune connexion candidate, aucun contournement de CAPTCHA ou de restrictions d’accès.')
    st.download_button('Exporter le diagnostic des sources', as_csv(source_rows), 'jobradar-sources.csv', 'text/csv')
    runs = store.runs(100)
    if runs:
        st.dataframe(runs, hide_index=True, width='stretch')

with history_tab:
    history = store.history(300)
    st.caption('300 dernières observations initiales ou modifications. Chaque source conserve ses propres versions avant déduplication. '
               'Le stockage local Streamlit peut être perdu au redémarrage ou au redéploiement : exportez les données ou utilisez un volume persistant.')
    if history:
        visible = [{k: row.get(k) for k in ('source_name', 'title', 'location', 'published_at', 'expires_at', 'observed_at', 'url')}
                   for row in history]
        st.dataframe(visible, hide_index=True, width='stretch')
        st.download_button('Exporter l’historique affiché (CSV)', as_csv(visible), 'jobradar-historique.csv', 'text/csv')
    else:
        st.caption('Aucune annonce enregistrée pour le moment.')

"""JobRadar V3 — real public job feeds, no candidate credentials.
Sources: Arbeitnow (Europe) and Remotive (remote). Neither guarantees Toulon coverage.
"""
from datetime import datetime, timezone
from urllib.parse import urlparse
import requests
import streamlit as st

st.set_page_config(page_title="JobRadar V3", page_icon="📡", layout="wide")

CATEGORIES = {
    "Tous les métiers": [],
    "Logistique / magasinage": ["logistique", "logistics", "magasinier", "warehouse", "cariste", "préparateur de commandes"],
    "Livraison VL": ["livreur", "delivery", "chauffeur", "driver", "courier"],
    "Manutention / industrie": ["manutention", "production", "manufacturing", "operator", "opérateur"],
    "Maintenance / technique": ["maintenance", "technicien", "technician", "mechanic"],
    "BTP / chantier": ["construction", "chantier", "building", "travaux", "site manager"],
    "Bureau d’études": ["engineering", "dessinateur", "projeteur", "métreur", "architect", "cad", "estimator"],
    "Accueil / restauration": ["hospitality", "restaurant", "reception", "serveur", "hotel"],
}

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "JobRadar/3.0 (public job feed reader)", "Accept": "application/json"})


def safe_url(url):
    p = urlparse(str(url or ""))
    return p.scheme == "https" and bool(p.netloc) and not p.username and not p.password


def normalize_arbeitnow(item):
    created = item.get("created_at")
    date = datetime.fromtimestamp(created, timezone.utc).date().isoformat() if isinstance(created, (int, float)) else ""
    return {"id": "arbeitnow:" + str(item.get("slug", "")), "title": item.get("title", ""),
            "company": item.get("company_name", ""), "location": item.get("location", ""),
            "contract": ", ".join(item.get("job_types") or []), "salary": "", "date": date,
            "url": item.get("url", ""), "source": "Arbeitnow", "remote": bool(item.get("remote"))}


def normalize_remotive(item):
    return {"id": "remotive:" + str(item.get("id", "")), "title": item.get("title", ""),
            "company": item.get("company_name", ""), "location": item.get("candidate_required_location", "Remote"),
            "contract": item.get("job_type", ""), "salary": item.get("salary", ""),
            "date": str(item.get("publication_date", ""))[:10], "url": item.get("url", ""),
            "source": "Remotive", "remote": True}


@st.cache_data(ttl=21600, show_spinner=False)
def fetch_jobs():
    jobs, errors, counts = [], [], {}
    endpoints = [
        ("Arbeitnow", "https://www.arbeitnow.com/api/job-board-api", "data", normalize_arbeitnow),
        ("Remotive", "https://remotive.com/api/remote-jobs", "jobs", normalize_remotive),
    ]
    for source, url, key, normalizer in endpoints:
        try:
            response = SESSION.get(url, timeout=20)
            response.raise_for_status()
            payload = response.json()
            raw = payload.get(key, [])
            if not isinstance(raw, list):
                raise ValueError("Format inattendu")
            clean = [normalizer(item) for item in raw if isinstance(item, dict)]
            clean = [item for item in clean if item["title"] and safe_url(item["url"])]
            counts[source] = len(clean)
            jobs.extend(clean)
        except (requests.RequestException, ValueError, KeyError, OverflowError) as exc:
            errors.append(f"{source} : {type(exc).__name__} — {str(exc)[:150]}")
            counts[source] = 0
    return jobs, errors, counts


def filter_jobs(jobs, sources, category, keywords, location):
    wanted = CATEGORIES[category]
    terms = [word.casefold() for word in keywords.split() if word.strip()]
    location = location.casefold().strip()
    results, seen = [], set()
    for job in jobs:
        if job["source"] not in sources:
            continue
        title = str(job["title"]).casefold()
        if wanted and not any(word in title for word in wanted):
            continue
        if terms and not all(word in (title + " " + str(job["company"]).casefold()) for word in terms):
            continue
        if location and location not in str(job["location"]).casefold():
            continue
        key = (title, str(job["company"]).casefold(), str(job["location"]).casefold())
        if key in seen:
            continue
        seen.add(key)
        results.append(job)
    return sorted(results, key=lambda item: item["date"], reverse=True)


st.title("📡 JobRadar")
st.caption("V3 · Annonces réellement récupérées depuis des API publiques · Aucun compte candidat, aucune clé")
st.warning("Couverture actuelle limitée : Arbeitnow publie surtout des emplois européens (notamment en Allemagne), Remotive des emplois à distance. Ces sources ne couvrent pas encore correctement l'intérim à Toulon.")
with st.sidebar:
    st.header("Recherche")
    category = st.selectbox("Métier", list(CATEGORIES))
    keywords = st.text_input("Mots-clés", placeholder="Ex. maintenance")
    location = st.text_input("Localisation exacte (vide = toutes)", value="", placeholder="Ex. Toulon, France")
    sources = st.multiselect("Sources réellement connectées", ["Arbeitnow", "Remotive"], default=["Arbeitnow", "Remotive"])
    if st.button("🔄 Actualiser les flux", use_container_width=True):
        fetch_jobs.clear()
    st.caption("Actualisation mise en cache 6 heures, pour respecter les limites des fournisseurs.")

with st.spinner("Récupération des annonces publiques…"):
    jobs, errors, counts = fetch_jobs()
for error in errors:
    st.error("Connexion impossible — " + error)
st.caption("Sources : " + " · ".join(f"{source} : {count} offres reçues" for source, count in counts.items()))
filtered = filter_jobs(jobs, sources, category, keywords, location)
st.metric("Annonces correspondant aux filtres", len(filtered))
if not filtered:
    st.info("Aucune annonce trouvée pour ces filtres dans les sources actuellement connectées. Essaie sans localisation ou avec « Tous les métiers ». Cela ne signifie pas qu'il n'existe aucune offre dans ta région.")
for job in filtered[:150]:
    with st.container(border=True):
        st.subheader(job["title"])
        st.write(f"**{job['company']}** · 📍 {job['location']}")
        st.caption(f"{job['source']} · {job['date'] or 'Date inconnue'} · {job['contract'] or 'Contrat non précisé'}" + (f" · {job['salary']}" if job['salary'] else ""))
        st.link_button("Voir l'annonce originale ↗", job["url"])
if len(filtered) > 150:
    st.caption("150 premières annonces affichées. Affine les filtres pour réduire la liste.")
st.divider()
st.caption("Confidentialité : aucun compte candidat, aucune saisie de mot de passe, aucun suivi personnel stocké. Les liens mènent aux plateformes d'origine. Les flux peuvent être incomplets ou indisponibles.")

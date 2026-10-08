import os, json, sqlite3, datetime, requests
import pandas as pd
import streamlit as st
from pathlib import Path

st.set_page_config(page_title='JobRadar', page_icon='📡', layout='wide')
DB = os.getenv('JOBRADAR_DB', 'jobradar.sqlite3')
CATEGORIES = {
 'Logistique / magasinage': ['préparateur de commandes','magasinier','cariste','agent logistique'],
 'Livraison VL': ['chauffeur livreur','livreur VL'],
 'Manutention / industrie': ['manutentionnaire','agent de production','opérateur de production'],
 'Maintenance / technique': ['technicien maintenance','agent de maintenance'],
 'BTP / chantier': ['ouvrier bâtiment','aide chantier','préparateur travaux'],
 'Bureau d’études': ['dessinateur projeteur','métreur','économiste construction'],
 'Accueil / restauration': ['agent accueil','serveur','employé restauration'],
}
SOURCES=['France Travail','Manpower','Adecco','Adéquat','Interaction','Crit','Samsic','Proman','Advance Emploi','Partnaire','Mistertemp','Gojob','Randstad','Synergie','Start People','RAS Intérim','Temporis','Actual','Triangle Intérim','Team Intérim','Staffmatch','Intérim Nation','Satis Jobs Center','R Intérim']

def db():
 c=sqlite3.connect(DB, check_same_thread=False)
 c.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, title TEXT, company TEXT, location TEXT, contract TEXT, salary TEXT, published TEXT, url TEXT, source TEXT, category TEXT, fetched TEXT)')
 c.execute('CREATE TABLE IF NOT EXISTS tracking (id TEXT PRIMARY KEY, status TEXT DEFAULT "À consulter")')
 c.commit();return c

def token():
 client=os.getenv('FRANCE_TRAVAIL_CLIENT_ID',''); secret=os.getenv('FRANCE_TRAVAIL_CLIENT_SECRET','')
 if not client or not secret: raise RuntimeError('Identifiants API France Travail absents : configurez FRANCE_TRAVAIL_CLIENT_ID et FRANCE_TRAVAIL_CLIENT_SECRET.')
 r=requests.post('https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire',data={'grant_type':'client_credentials','client_id':client,'client_secret':secret,'scope':'api_offresdemploiv2 o2dsoffre'},timeout=20)
 r.raise_for_status();return r.json()['access_token']

def fetch_ft(categories, dept, max_per_query=75):
 bearer=token(); headers={'Authorization':f'Bearer {bearer}','Accept':'application/json'}
 results={};errors=[]
 for category in categories:
  for keyword in CATEGORIES[category]:
   try:
    params={'motsCles':keyword,'departement':dept,'range':f'0-{max_per_query-1}'}
    r=requests.get('https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search',headers=headers,params=params,timeout=25)
    if r.status_code==204:continue
    r.raise_for_status()
    for x in r.json().get('resultats',[]):
     key='ft:'+str(x.get('id'))
     loc=x.get('lieuTravail') or {}
     company=(x.get('entreprise') or {}).get('nom','Non précisée')
     results[key]=(key,x.get('intitule',''),company,loc.get('libelle',''),x.get('typeContratLibelle',''),x.get('salaire',{}).get('libelle',''),x.get('dateCreation',''),x.get('origineOffre',{}).get('urlOrigine') or 'https://candidat.francetravail.fr/offres/recherche/detail/'+str(x.get('id')), 'France Travail',category,datetime.datetime.now(datetime.timezone.utc).isoformat())
   except Exception as e:errors.append(f'{keyword}: {e}')
 return list(results.values()),errors

conn=db()
st.title('📡 JobRadar')
st.caption('Agrégateur d’offres publiques — version initiale. Les autres agences sont référencées mais leur collecte n’est pas encore connectée.')
with st.sidebar:
 st.header('Recherche')
 chosen=st.multiselect('Métiers',list(CATEGORIES),default=list(CATEGORIES))
 dept=st.text_input('Département (code)',value='83')
 query=st.text_input('Filtrer les résultats par mot-clé')
 sources=st.multiselect('Source',SOURCES,default=['France Travail'])
 status=st.multiselect('Suivi', ['À consulter','Favori','Candidature envoyée','Relance','Refus'])
 st.divider()
 if st.button('🔄 Actualiser maintenant',type='primary',use_container_width=True):
  if not chosen:st.warning('Sélectionne au moins une catégorie.')
  else:
   with st.spinner('Recherche des offres en cours…'):
    try:
     rows,errors=fetch_ft(chosen,dept)
     conn.executemany('INSERT OR REPLACE INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?)',rows)
     conn.commit()
     st.success(f'{len(rows)} offres récupérées ou mises à jour via France Travail.')
     if errors:st.warning(f'{len(errors)} recherches ont échoué. Exemple : {errors[0]}')
    except Exception as e:st.error(str(e))
 st.caption('La collecte quotidienne peut être programmée sur un hébergement externe ; elle n’est pas active dans cette version locale.')
rows=conn.execute('SELECT j.*, COALESCE(t.status,"À consulter") AS status FROM jobs j LEFT JOIN tracking t ON j.id=t.id ORDER BY j.published DESC').fetchall()
cols=[x[1] for x in conn.execute('PRAGMA table_info(jobs)').fetchall()]+['status']
df=pd.DataFrame(rows,columns=cols)
if not df.empty:
 if chosen:df=df[df.category.isin(chosen)]
 if sources:df=df[df.source.isin(sources)]
 if query:df=df[df[['title','company','location']].fillna('').apply(lambda x:x.str.contains(query,case=False,regex=False)).any(axis=1)]
 if status:df=df[df.status.isin(status)]
st.metric('Offres affichées',len(df))
if df.empty:st.info('Aucune offre enregistrée pour ces filtres. Configure les identifiants France Travail puis clique sur « Actualiser maintenant ».')
else:
 for x in df.head(250).to_dict('records'):
  with st.container(border=True):
   st.subheader(x['title'])
   st.write(f"📍 {x['location']} · {x['company']} · {x['contract'] or 'Contrat non précisé'}")
   st.caption(f"{x['source']} · {x['category']} · {x['published'][:10]} · {x['salary'] or 'Salaire non précisé'}")
   a,b=st.columns([1,2])
   a.link_button('Voir l’annonce ↗',x['url'])
   choices=['À consulter','Favori','Candidature envoyée','Relance','Refus']
   new=b.selectbox('Suivi',choices,index=choices.index(x['status']) if x['status'] in choices else 0,key='s'+x['id'],label_visibility='collapsed')
   if new!=x['status']:
    conn.execute('INSERT OR REPLACE INTO tracking(id,status) VALUES (?,?)',(x['id'],new));conn.commit()

"""Agency scope from Git 2920f5b; access decisions documented in docs/SOURCES.md."""
from dataclasses import replace
from .models import Source

AGENCIES = [
    ('manpower', 'Manpower', 'manpower.fr'),
    ('adecco', 'Adecco', 'adecco.fr'),
    ('adequat', 'Adéquat', 'lejobadequat.com'),
    ('interaction', 'Interaction', 'interaction-interim.com'),
    ('crit', 'Crit', 'crit-job.com'),
    ('samsic', 'Samsic', 'samsic-emploi.fr'),
    ('proman', 'Proman', 'proman-emploi.fr'),
    ('advance', 'Advance Emploi', 'advance-emploi.com'),
    ('partnaire', 'Partnaire', 'partnaire.fr'),
    ('mistertemp', "Mistertemp'", 'mistertemp.com'),
    ('gojob', 'Gojob', 'gojob.com'),
    ('randstad', 'Randstad', 'randstad.fr'),
    ('synergie', 'Synergie', 'synergie.fr'),
    ('startpeople', 'Start People', 'startpeople.fr'),
    ('ras', 'R.A.S Intérim', 'ras-interim.fr'),
    ('temporis', 'Temporis', 'temporis-franchise.fr'),
    ('actual', 'Actual', 'groupeactual.eu'),
    ('triangle', 'Triangle Intérim', 'triangle.fr'),
    ('team', 'Team Intérim', 'team-interim.fr'),
    ('staffmatch', 'Staffmatch', 'staffmatch.com'),
    ('interimnation', 'Intérim Nation', 'interim-nation.fr'),
    ('satis', 'Satis Jobs Center', 'satis-jobscenter.com'),
    ('regional', 'R Intérim', 'regional-interim.fr'),
]

SOURCES = [Source('territorial', 'Emploi-Territorial (Var)',
                  ('www.emploi-territorial.fr', 'emploi-territorial.fr'),
                  'https://www.emploi-territorial.fr/rss?search-dept=083',
                  kind='rss', enabled=True, access_review='public_rss', var_scope=True)] + [
    Source(identifier, name, (domain, 'www.' + domain), 'https://www.' + domain + '/')
    for identifier, name, domain in AGENCIES
]

# Explicit restrictions encountered during the 2026-10-08 review.
RESTRICTED_TERMS = {
    'adecco': 'https://www.adecco.com/fr-fr/conditions-generales',
    'manpower': 'https://www.manpower.fr/contenu-statique/conditions-generales-d-utilisation',
    'adequat': 'https://www.lejobadequat.com/mentions-legales',
    'interaction': 'https://www.interaction-interim.com/mentions-legales',
    'crit': 'https://www.crit-job.com/conditions-generales-utilisation/',
    'samsic': 'https://www.samsic-emploi.fr/cgu',
    'proman': 'https://www.proman-emploi.fr/cgu',
    'partnaire': 'https://www.partnaire.fr/conditions-generales-dutilisation/',
    'mistertemp': 'https://www.mistertemp.com/conditions-generales/',
    'gojob': 'https://gojob.com/cgu-cgv/',
    'randstad': 'https://www.randstad.fr/mentions-legales/',
    'synergie': 'https://www.synergie.fr/mentions-legales',
    'startpeople': 'https://www.startpeople.fr/mentions-legales',
    'ras': 'https://www.ras-interim.fr/cgu',
    'temporis': 'https://www.temporis-franchise.fr/mentions-legales',
    'actual': 'https://www.actualgroup.com/mentions-legales',
    'team': 'https://team-interim.fr/CGU/site-internet',
    'staffmatch': 'https://staffmatch.com/fr/legal/',
    'interimnation': 'https://interim-nation.fr/mentions-legales/',
    'satis': 'https://satis-jobscenter.com/mentions-legales/',
}
SOURCES = [replace(s, access_review='restricted', terms_url=RESTRICTED_TERMS[s.id],
                   review_note='Réutilisation/extraction restreinte par les conditions examinées ; autorisation nécessaire pour cet agrégateur.')
           if s.id in RESTRICTED_TERMS else s for s in SOURCES]
SOURCES = [replace(s, domains=s.domains + ('adecco.com', 'www.adecco.com'),
                   url='https://www.adecco.com/fr-fr') if s.id == 'adecco' else
           replace(s, domains=s.domains + ('actualgroup.com', 'www.actualgroup.com'),
                   url='https://www.actualgroup.com/') if s.id == 'actual' else s for s in SOURCES]
SOURCES = [replace(s, kind='wordpress', enabled=True, access_review='approved',
                   url='https://www.triangle.fr/wp-json/wp/v2/job?search=Toulon&per_page=100&orderby=date&order=desc',
                   terms_url='https://www.triangle.fr/politique-de-confidentialite/',
                   review_note='API publique et permaliens testés ; scope Toulon, posts WordPress seulement. AJAX interdit, jamais utilisé.')
           if s.id == 'triangle' else s for s in SOURCES]

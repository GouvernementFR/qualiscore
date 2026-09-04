# Qualiscore

Qualiscore est un outil en ligne de commande qui audite les sites web selon plusieurs indicateurs de qualité (accessibilité, conformité au DSFR, éco-conception, sécurité, liens brisés, RGPD) et produit un rapport JSON unifié.

## Contexte

Le Service d'information du Gouvernement (SIG), service du Premier ministre, est responsable de l'innovation et de la transformation numérique de la communication. À ce titre, il pilote le Système de Design de l'État (DSFR), aujourd'hui déployé sur plus de 2 000 sites publics, instruit les demandes d'agrément des sites de l'État et de leurs URL en .gouv.fr, et veille à la lisibilité comme à la qualité de l'offre numérique de l'État pour les usagers.

La circulaire n° 6411/SG du 7 juillet 2023, relative à l'amélioration de la lisibilité des sites Internet de l'État et de la qualité des démarches numériques, fixe le cadre de cette exigence : identité de l'État, accessibilité, sécurité, protection des données personnelles, éco-conception. Pour en suivre l'application, le SIG cartographie les sites de l'État ouverts au public et mesure régulièrement une série d'indicateurs de qualité.

Qualiscore est l'outil qui produit cette mesure. Le SIG le publie en logiciel libre pour deux raisons. D'une part, permettre aux administrations d'auditer elles-mêmes les sites que le SIG ne peut pas analyser depuis l'extérieur :
intranets, extranets, environnements de recette, services derrière authentification. D'autre part, ouvrir le code à celles et ceux qui souhaitent l'améliorer, ajouter des indicateurs ou affiner les méthodes de calcul. En publiant Qualiscore, le SIG contribue aux communs numériques de l'État.

Retrouvez d'ores et déjà la cartographie et les indicateurs des sites publics sur l'outil audience.communication.gouv.fr.

## Prérequis

**Python ≥ 3.14** et **Node.js** doivent être installés sur le système.

### Dépendances Python

Installation avec [uv](https://docs.astral.sh/uv/) ou pip :

```bash
uv sync
# ou
pip install -r requirements.txt
```

Principaux paquets Python utilisés :

| Paquet                        | Utilisé par                                     |
|-------------------------------|-------------------------------------------------|
| `pyyaml`                      | découverte des outils (`registry.py`)           |
| `niquests`                    | récupération des versions DSFR (`registry.py`)  |
| `camoufox` + `beautifulsoup4` | outil `dom`                                     |
| `playwright`                  | outil `dom` + chemin Chromium pour `lighthouse` |
| `ecoindex-scraper`            | outil `ecoindex`                                |

Après l'installation des paquets Python, installez les navigateurs Playwright :

```bash
python -m playwright install chromium
python -m camoufox fetch
```

### Dépendances Node.js

```bash
npm install
```

Installe :

| Paquet                                                    | Utilisé par         |
|-----------------------------------------------------------|---------------------|
| `lighthouse`                                              | outil `lighthouse`  |
| `@mdn/mdn-http-observatory` (`mdn-http-observatory-scan`) | outil `observatory` |
| `wget-parser`                                             | outil `404`         |

L'outil `404` nécessite également que `wget` soit installé sur le système.

---

## Utilisation

```bash
# Lister les outils disponibles
python main.py list

# Exécuter tous les outils sur une ou plusieurs URL
python main.py run --url example.com --url other.com

# Exécuter uniquement certains outils
python main.py run -t dom -t lighthouse --url example.com

# Charger des URL depuis un fichier (une par ligne)
python main.py run --urls-file urls.txt

# Générer le rapport à partir des données collectées
python main.py report
```

---

## Docker

### Construction

```bash
docker compose build
```

L'image est basée sur `mcr.microsoft.com/playwright/python` et inclut toutes les dépendances Python et Node.js, Camoufox, Chromium et `wget`.

### Exécution avec Docker Compose (recommandé)

`compose.yaml` monte `./data` dans le conteneur afin que les résultats soient conservés sur l'hôte.

```bash
# Construire et démarrer
docker compose up -d --build

# Exécuter une commande (le conteneur s'arrête à la fin)
docker compose run --rm qualiscore list
docker compose run --rm qualiscore run --url example.com
docker compose run --rm qualiscore run --url example.com --url other.com -t dom -t lighthouse
docker compose run --rm qualiscore report
```

### Exécution avec `docker run`

```bash
# Construire d'abord l'image
docker build -t qualiscore .

# Monter le répertoire local data/ pour conserver les résultats
docker run --rm -v "$(pwd)/data:/app/data" qualiscore list
docker run --rm -v "$(pwd)/data:/app/data" qualiscore run --url example.com
docker run --rm -v "$(pwd)/data:/app/data" qualiscore report
```

> Le répertoire `data/` est monté afin que les résultats d'analyse et le rapport généré soient écrits sur l'hôte, et non perdus à la fermeture du conteneur.

---

## Fonctionnement

### Découverte des outils

`registry.py` parcourt le dossier `tools/` à la recherche de sous-répertoires contenant un fichier `tool.yaml`. Chaque fichier YAML déclare :

- `name` : identifiant utilisé en ligne de commande
- `entrypoint` : commande à exécuter (par exemple `bash main.sh`, `python main.py`)
- `concurrency_factor` *(facultatif)* : contrôle le nombre de places occupées par l'outil dans le pool partagé de workers (par défaut `1`). Les valeurs > 1 indiquent un outil léger pouvant être exécuté en parallèle davantage ; les valeurs < 1 (par exemple `0.2` pour Lighthouse) indiquent un outil lourd qui limite davantage la concurrence.

### Orchestrateur

`runner.py` construit une liste de tâches `(outil, url)` et les exécute en parallèle via `ThreadPoolExecutor`. Un sémaphore pondéré applique le budget `concurrency_factor` afin d'éviter qu'un outil lourd ne surcharge la machine.

Chaque outil reçoit l'URL cible comme premier argument et doit écrire son JSON de sortie dans `data/<hostname>/`.

---

## Outils

### `404` — Vérification des liens brisés

**Entrypoint :** `bash main.sh`  
**Dépend de :** `wget` (système), `wget-parser` (npm)

Parcourt le site jusqu'à 5 niveaux de profondeur avec `wget --spider` puis traite la sortie via `wget-parser` pour produire :

```json
{ "links": [...], "broken": [...] }
```

Sortie : `data/<host>/errors_404.json`

---

### `dom` — Analyse du DOM (DSFR, RGAA, RGPD, suivi)

**Entrypoint :** `python main.py`  
**Dépend de :** `camoufox`, `beautifulsoup4`, `playwright`

Lance un navigateur furtif (Camoufox) et extrait quatre jeux de données depuis la page :

- **DSFR** — détecte `.fr-header__brand`, lit la version depuis les fichiers CSS chargés ou `window.dsfr.version`.
- **RGAA** — suit le lien « accessibilité », récupère la mention de conformité, le pourcentage, la version du RGAA et la date de mise à jour.
- **RGPD** — recherche les liens correspondant à « mentions légales » (`ml`), « politique de confidentialité » (`pc`) et « CGU » (`cgu`), puis attribue un score selon la présence et la couverture des mots-clés.
- **Suivi** — analyse les scripts inline à la recherche d'empreintes d'Eulerian, Matomo, Piwik, Piano et Google Analytics.

Sorties : `data/<host>/dsfr.json`, `rgaa.json`, `gdpr.json`, `tracking.json`

---

### `ecoindex` — Score d'éco-conception

**Entrypoint :** `python main.py`  
**Dépend de :** `ecoindex-scraper`

Utilise `EcoindexScraper` pour charger la page et calculer un score (0–100) basé sur la taille du DOM, le nombre de requêtes et le poids de la page.

Sortie : `data/<host>/ecoindex.json`

---

### `lighthouse` — Qualité web (Lighthouse)

**Entrypoint :** `bash main.sh`  
**Dépend de :** `lighthouse` (npm), `playwright` (pour le chemin Chromium)

Localise le binaire Chromium géré par Playwright et lance `lighthouse` en mode sans tête pour produire un rapport JSON complet.

**Remarque :** `concurrency_factor: 0.2` — Lighthouse consomme beaucoup de CPU ; une seule instance s'exécute environ toutes les 5 places de worker.

Sortie : `data/<host>/lighthouse.json`

---

### `observatory` — En-têtes HTTP de sécurité (MDN Observatory)

**Entrypoint :** `bash main.sh`  
**Dépend de :** `@mdn/mdn-http-observatory` (npm)

Exécute `mdn-http-observatory-scan` sur le nom d'hôte et enregistre le résultat.

Sortie : `data/<host>/observatory.json`

---

## Génération du rapport

L'exécution de `python main.py report` lit tous les fichiers JSON situés sous `data/` et produit `data/report.json` — une liste d'entrées par site, chacune contenant un objet `summary`.

### Calcul des scores par indicateur

| Indicateur      | Champ(s)                                                                                                                           | Calcul du score (0–100)                                                                                                                                                                                                                                                                                                                                                                                                                                           |
|-----------------|------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **errors_404**  | `errors_404`, `errors_404_count`                                                                                                   | `(1 − broken/total) × 100`. `errors_404_count` conserve le nombre brut de liens cassés.                                                                                                                                                                                                                                                                                                                                                                           |
| **DSFR**        | `dsfr`                                                                                                                             | 50 points pour la présence de `.fr-header__brand`. Jusqu'à 50 points supplémentaires selon l'ancienneté de la version DSFR via une courbe d'atténuation douce (`50 × (1 - (i/N)^{0.8})`, où `i` est l'indice de la version dans la liste triée des versions publiées). 5 points si une version est détectée mais inconnue ou trop ancienne. Les versions DSFR sont récupérées via l'API GitHub et mises en cache dans `data/dsfr_versions.json` pendant 30 jours. |
| **RGAA**        | `rgaa`                                                                                                                             | Utilise `percentage` s'il est présent. Sinon, s'appuie sur la détection de mots-clés : « totalement conforme » → 100, « partiellement conforme » → 50, « non conforme » → 0.                                                                                                                                                                                                                                                                                      |
| **RGPD** (×3)   | `gdpr_ml`, `gdpr_pc`, `gdpr_cgu`                                                                                                   | 50 points si le lien correspondant existe + jusqu'à 50 points pour la couverture des mots-clés : `len(matches) / (len(matches) + len(missing)) × 50`.                                                                                                                                                                                                                                                                                                             |
| **Lighthouse**  | `lighthouse_performance`, `lighthouse_accessibility`, `lighthouse_best-practices`, `lighthouse_seo`, `lighthouse_agentic-browsing` | Transmission directe des scores de catégories Lighthouse × 100.                                                                                                                                                                                                                                                                                                                                                                                                   |
| **Observatory** | `observatory`                                                                                                                      | Transmission directe de `scan.score`.                                                                                                                                                                                                                                                                                                                                                                                                                             |
| **Ecoindex**    | `ecoindex`                                                                                                                         | Transmission directe du champ `score`.                                                                                                                                                                                                                                                                                                                                                                                                                            |
| **Suivi**       | `tracking`                                                                                                                         | Nom du premier outil d'analyse détecté, ou `null` si aucun n'est trouvé.                                                                                                                                                                                                                                                                                                                                                                                          |

Le champ `date` de chaque entrée est défini à partir de la date d'analyse fournie par ecoindex, observatory ou tracking lorsque disponible, sinon à l'instant courant.

---

## Organisation des données

```
data/
  <hostname>/
    dsfr.json
    rgaa.json
    gdpr.json
    tracking.json
    ecoindex.json
    errors_404.json
    lighthouse.json
    observatory.json
    screenshot.png
  dsfr_versions.json   ← liste des versions DSFR mises en cache (rafraîchie tous les 30 jours)
  report.json          ← généré par `python main.py report`
```

# Qualiscore

Qualiscore is a CLI tool that audits websites across multiple quality indicators (accessibility, DSFR compliance, eco-design, security, broken links, GDPR) and produces a unified JSON report.

## Requirements

**Python ≥ 3.14** and **Node.js** must be available on the system.

### Python dependencies

Install with [uv](https://docs.astral.sh/uv/) or pip:

```bash
uv sync
# or
pip install -r requirements.txt
```

Key Python packages used:

| Package                       | Used by                                     |
|-------------------------------|---------------------------------------------|
| `pyyaml`                      | tool discovery (`registry.py`)              |
| `niquests`                    | DSFR versions fetch (`registry.py`)         |
| `camoufox` + `beautifulsoup4` | `dom` tool                                  |
| `playwright`                  | `dom` tool + Chromium path for `lighthouse` |
| `ecoindex-scraper`            | `ecoindex` tool                             |

After installing Python packages, install the Playwright browsers:

```bash
python -m playwright install chromium
python -m camoufox fetch
```

### Node.js dependencies

```bash
npm install
```

Provides:

| Package                                                   | Used by            |
|-----------------------------------------------------------|--------------------|
| `lighthouse`                                              | `lighthouse` tool  |
| `@mdn/mdn-http-observatory` (`mdn-http-observatory-scan`) | `observatory` tool |
| `wget-parser`                                             | `404` tool         |

The `404` tool also requires `wget` to be installed system-wide.

---

## Usage

```bash
# List available tools
python main.py list

# Run all tools against one or more URLs
python main.py run --url example.com --url other.com

# Run specific tools only
python main.py run -t dom -t lighthouse --url example.com

# Load URLs from a file (one per line)
python main.py run --urls-file urls.txt

# Generate the report from collected data
python main.py report
```

---

## Docker

### Build

```bash
docker compose build
```

The image is based on `mcr.microsoft.com/playwright/python` and bundles all Python and Node.js dependencies, Camoufox, Chromium, and `wget`.

### Run with Docker Compose (recommended)

`compose.yaml` mounts `./data` into the container so results persist on the host.

```bash
# Build and start
docker compose up -d --build

# Run a command (the container exits when done)
docker compose run --rm qualiscore list
docker compose run --rm qualiscore run --url example.com
docker compose run --rm qualiscore run --url example.com --url other.com -t dom -t lighthouse
docker compose run --rm qualiscore report
```

### Run with `docker run`

```bash
# Build the image first
docker build -t qualiscore .

# Mount the local data/ directory to persist results
docker run --rm -v "$(pwd)/data:/app/data" qualiscore list
docker run --rm -v "$(pwd)/data:/app/data" qualiscore run --url example.com
docker run --rm -v "$(pwd)/data:/app/data" qualiscore report
```

> The `data/` directory is mounted so that scan results and the generated report are written to the host rather than discarded with the container.

---

## How it works

### Tool discovery

`registry.py` scans the `tools/` directory for sub-directories containing a `tool.yaml` file. Each YAML file declares:

- `name`: identifier used on the CLI
- `entrypoint`: command to run (e.g. `bash main.sh`, `python main.py`)
- `concurrency_factor` *(optional)*: controls how many slots the tool occupies in the shared worker pool (default `1`). Values > 1 mean the tool is lightweight and can run more in parallel; values < 1 (e.g. `0.2` for Lighthouse) mean it is heavy and limits concurrency.

### Runner

`runner.py` builds a task list of `(tool, url)` pairs and executes them concurrently using a `ThreadPoolExecutor`. A weighted semaphore enforces the `concurrency_factor` budget so heavy tools do not overwhelm the machine.

Each tool receives the target URL as its first argument and is responsible for writing its output JSON under `data/<hostname>/`.

---

## Tools

### `404` — Broken link checker

**Entrypoint:** `bash main.sh`  
**Depends on:** `wget` (system), `wget-parser` (npm)

Crawls the site up to 5 levels deep using `wget --spider` and pipes the output through `wget-parser` to produce:

```json
{ "links": [...], "broken": [...] }
```

Output: `data/<host>/errors_404.json`

---

### `dom` — DOM analysis (DSFR, RGAA, GDPR, tracking)

**Entrypoint:** `python main.py`  
**Depends on:** `camoufox`, `beautifulsoup4`, `playwright`

Launches a stealth browser (Camoufox) and extracts four datasets from the page:

- **DSFR** – detects `.fr-header__brand`, reads version from loaded CSS files or `window.dsfr.version`.
- **RGAA** – follows the "accessibilité" link, scrapes conformance mention, percentage, RGAA version, and update date.
- **GDPR** – looks for links matching "mentions légales" (`ml`), "politique de confidentialité" (`pc`), and "CGU" (`cgu`), then scores presence + keyword coverage.
- **Tracking** – scans inline scripts for fingerprints of Eulerian, Matomo, Piwik, Piano, and Google Analytics.

Outputs: `data/<host>/dsfr.json`, `rgaa.json`, `gdpr.json`, `tracking.json`

---

### `ecoindex` — Eco-design score

**Entrypoint:** `python main.py`  
**Depends on:** `ecoindex-scraper`

Uses `EcoindexScraper` to load the page and compute a score (0–100) based on DOM size, number of requests, and page weight.

Output: `data/<host>/ecoindex.json`

---

### `lighthouse` — Web quality (Lighthouse)

**Entrypoint:** `bash main.sh`  
**Depends on:** `lighthouse` (npm), `playwright` (for the Chromium path)

Locates the Playwright-managed Chromium binary and runs `lighthouse` in headless mode to produce a full JSON report.

**Note:** `concurrency_factor: 0.2` — Lighthouse is CPU-intensive; only one instance runs per ~5 worker slots.

Output: `data/<host>/lighthouse.json`

---

### `observatory` — HTTP security headers (MDN Observatory)

**Entrypoint:** `bash main.sh`  
**Depends on:** `@mdn/mdn-http-observatory` (npm)

Runs `mdn-http-observatory-scan` against the hostname and saves the result.

Output: `data/<host>/observatory.json`

---

## Report generation

Running `python main.py report` reads all JSON files under `data/` and produces `data/report.json` — a list of per-site entries, each containing a `summary` object.

### Scoring per indicator

| Indicator       | Field(s)                                                                                                                           | How the score (0–100) is computed                                                                                                                                                                                                                                                                                                                                              |
|-----------------|------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **errors_404**  | `errors_404`, `errors_404_count`                                                                                                   | `(1 − broken/total) × 100`. `errors_404_count` stores the raw broken-link count.                                                                                                                                                                                                                                                                                               |
| **DSFR**        | `dsfr`                                                                                                                             | 50 pts for having `.fr-header__brand`. Up to 50 additional pts based on DSFR version recency using a soft power-decay curve ($50 \times (1 - (i/N)^{0.8})$, where $i$ is the version index in the sorted release list). 5 pts if a version is detected but unknown/too old. DSFR versions are fetched from the GitHub API and cached in `data/dsfr_versions.json` for 30 days. |
| **RGAA**        | `rgaa`                                                                                                                             | Uses `rgaa_percentage` if present. Falls back to keyword matching: "totalement conforme" → 100, "partiellement conforme" → 50, "non conforme" → 0.                                                                                                                                                                                                                             |
| **GDPR** (×3)   | `gdpr_ml`, `gdpr_pc`, `gdpr_cgu`                                                                                                   | 50 pts if the relevant link exists + up to 50 pts for keyword coverage: `len(matches) / (len(matches) + len(missing)) × 50`.                                                                                                                                                                                                                                                   |
| **Lighthouse**  | `lighthouse_performance`, `lighthouse_accessibility`, `lighthouse_best-practices`, `lighthouse_seo`, `lighthouse_agentic-browsing` | Direct pass-through of Lighthouse category scores × 100.                                                                                                                                                                                                                                                                                                                       |
| **Observatory** | `observatory`                                                                                                                      | Direct pass-through of `scan.score`.                                                                                                                                                                                                                                                                                                                                           |
| **Ecoindex**    | `ecoindex`                                                                                                                         | Direct pass-through of the `score` field.                                                                                                                                                                                                                                                                                                                                      |
| **Tracking**    | `tracking`                                                                                                                         | Name of the first detected analytics tool, or `null` if none found.                                                                                                                                                                                                                                                                                                            |

The `date` field on each entry is set to the scan date from ecoindex, observatory, or tracking data when available, otherwise the current time.

---

## Data layout

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
  dsfr_versions.json   ← cached DSFR release list (refreshed every 30 days)
  report.json          ← generated by `python main.py report`
```

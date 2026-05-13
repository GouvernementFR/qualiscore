import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from registry import retrieve_dsfr_versions

SUBTOOLS = {
    "dom": ["dsfr", "rgaa", "gdpr", "tracking"],
    "404": ["errors_404"],
}


@dataclass
class SummaryEntry:
    dsfr: int | None = None
    ecoindex: int | None = None
    errors_404: int | None = None
    errors_404_count: int | None = None
    gdpr_cgu: int | None = None
    gdpr_ml: int | None = None
    gdpr_pc: int | None = None
    lighthouse_accessibility: int | None = None
    lighthouse_best_practices: int | None = None
    lighthouse_performance: int | None = None
    lighthouse_seo: int | None = None
    observatory: int | None = None
    rgaa: int | None = None
    tracking: int | None = None


@dataclass
class ReportEntry:
    def to_dict(self) -> dict:
        result = asdict(self)
        result["summary"] = {
            ("lighthouse_best-practices" if key == "lighthouse_best_practices" else key): value
            for key, value in result.get("summary", {}).items()
        }
        return result

    url: str
    date: datetime
    summary: SummaryEntry


def get_dsfr_versions() -> dict:
    if Path("data/dsfr_versions.json").exists():
        with Path("data/dsfr_versions.json").open(encoding="utf-8") as file:
            versions = json.load(file)
            if date.fromisoformat(versions["fetched_at"]) >= date.today() - timedelta(days=30):
                return versions["versions"]

    print("DSFR versions data not found or outdated, fetching latest versions...")
    versions = retrieve_dsfr_versions()
    with Path("data/dsfr_versions.json").open("w", encoding="utf-8") as file:
        json.dump(versions, file, indent=2, ensure_ascii=False, default=str)

    return versions["versions"]


def generate_report(data: dict, tools: list) -> None:
    dsfr_versions = get_dsfr_versions()
    report = []
    for site, paths in data.items():
        print(f"Site: {site}")

        site_summary = ReportEntry(
            url="https://" + site,
            date=datetime.now().replace(microsecond=0),
            summary=SummaryEntry(),
        )

        all_tools = set(tools)
        for parent, subs in SUBTOOLS.items():
            if parent in all_tools:
                all_tools.remove(parent)
                all_tools.update(subs)
        found_tools = set()

        for path in sorted(paths):
            found_tools.add(path.stem)
            print(f"  [✓] {path.stem}")
            content = path.read_text(encoding="utf-8")
            results = json.loads(content if content else "{}")
            match path.stem:
                case "errors_404":
                    total_links = len(results.get("links", []))
                    broken_links = len(results.get("broken", []))
                    score = (1 - broken_links / total_links) * 100 if total_links else 0
                    site_summary.summary.errors_404 = int(round(score, 0))
                    site_summary.summary.errors_404_count = broken_links
                case "rgaa":
                    score = results.get("rgaa_percentage")
                    if score is None and results.get("mention"):
                        mention = results.get("mention", "").lower()
                        if "totalement conforme" in mention:
                            score = 100
                        elif "partiellement conforme" in mention:
                            score = 50
                        elif "non conforme" in mention:
                            score = 0
                    if not score:
                        score = 0
                    site_summary.summary.rgaa = int(round(score, 0))
                case "dsfr":
                    score = 50 if results.get("header_brand") else 0
                    if f"v{results.get('version')}" in dsfr_versions:
                        index = list(dsfr_versions.keys()).index(f"v{results.get('version')}")
                        # the more recent the version, the higher the score (max 50 points)
                        # use a soft decay so recent versions keep a high score and slightly older versions are not penalized too harshly
                        # the curve should hit 0 at max index while keeping latest versions near the top
                        score += 50 * (1 - (min(index, len(dsfr_versions)) / len(dsfr_versions)) ** 0.8)
                    else:
                        # small score for using DSFR even if version is unknown or too old
                        score += 5 if results.get("version") else 0
                    site_summary.summary.dsfr = int(round(score, 0))
                case "ecoindex":
                    score = results.get("score", 0)
                    site_summary.summary.ecoindex = int(round(score, 0))
                    scan_date = results.get("date")
                    if scan_date:
                        date_obj = datetime.strptime(scan_date, "%Y-%m-%d %H:%M:%S.%f")
                        site_summary.date = date_obj.replace(microsecond=0)
                case "gdpr":
                    for key in ["ml", "pc", "cgu"]:
                        score = 50 if results.get(f"{key}_url") else 0
                        matches = results.get(f"{key}_matches", [])
                        missing = results.get(f"{key}_missing", [])
                        if matches or missing:
                            score += 50 * (len(matches) / (len(matches) + len(missing)))
                        setattr(site_summary.summary, f"gdpr_{key}", int(round(score, 0)))
                case "lighthouse":
                    for category in results.get("categories", []):
                        score = (results["categories"][category]["score"] or 0) * 100
                        setattr(site_summary.summary, f"lighthouse_{category.replace('-', '_')}", int(round(score, 0)))
                case "observatory":
                    score = results.get("scan", {}).get("score", 0)
                    site_summary.summary.observatory = int(round(score, 0))
                    scan_date = results.get("scan", {}).get("responseHeaders", {}).get("date")
                    if scan_date:
                        try:
                            date_obj = datetime.strptime(scan_date, "%a, %d %b %Y %H:%M:%S %Z")
                            site_summary.date = date_obj.replace(microsecond=0)
                        except ValueError:
                            logger.warning("  [⨯] Invalid date format: %s", scan_date)
                case "tracking":
                    site_summary.summary.tracking = results.get("tools")[0] if results.get("tools") else None
                    scan_date = results.get("date")
                    if scan_date:
                        date_obj = datetime.strptime(scan_date, "%Y-%m-%d %H:%M:%S.%f")
                        site_summary.date = date_obj.replace(microsecond=0)
                case _:
                    continue

        for tool in all_tools:
            if tool not in found_tools:
                print(f"  [⨯] {tool} (no data)")

        report.append(site_summary.to_dict())

    with Path("data/report.json").open("w", encoding="utf-8") as report_file:
        json.dump(report, report_file, indent=2, ensure_ascii=False, default=str)

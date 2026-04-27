import json
from datetime import date, datetime, timedelta
from pathlib import Path

from registry import retrieve_dsfr_versions


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
        site_summary = {
            "url": "https://" + site,
            "date": None,
            "summary": {},
        }
        available_tools = set()

        for path in sorted(paths):
            available_tools.add(path.stem)
            print(f"  [✓] {path.stem}")
            results = json.loads(path.read_text())
            match path.stem:
                case "errors_404":
                    total_links = len(results.get("links", []))
                    broken_links = len(results.get("broken", []))
                    score = (1 - broken_links / total_links) * 100 if total_links else 0
                    site_summary["summary"]["errors_404"] = int(round(score, 0))
                    site_summary["summary"]["errors_404_count"] = broken_links
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
                    site_summary["summary"]["rgaa"] = int(round(score, 0))
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
                    site_summary["summary"]["dsfr"] = int(round(score, 0))
                case "ecoindex":
                    score = results.get("score", 0)
                    site_summary["summary"]["ecoindex"] = int(round(score, 0))
                    scan_date = results.get("date")
                    if scan_date:
                        date_obj = datetime.strptime(scan_date, "%Y-%m-%d %H:%M:%S.%f")
                        site_summary["date"] = date_obj.replace(microsecond=0) if scan_date else None
                case "gdpr":
                    for key in ["ml", "pc", "cgu"]:
                        score = 50 if results.get(f"{key}_url") else 0
                        matches = results.get(f"{key}_matches", [])
                        missing = results.get(f"{key}_missing", [])
                        if matches or missing:
                            score += 50 * (len(matches) / (len(matches) + len(missing)))
                        site_summary["summary"][f"gdpr_{key}"] = int(round(score, 0))
                case "lighthouse":
                    for category in results.get("categories", []):
                        score = results["categories"][category]["score"] * 100
                        site_summary["summary"][f"lighthouse_{category}"] = int(round(score, 0))
                case "observatory":
                    score = results.get("scan", {}).get("score", 0)
                    site_summary["summary"]["observatory"] = int(round(score, 0))
                    scan_date = results.get("scan", {}).get("responseHeaders", {}).get("date")
                    if scan_date:
                        date_obj = datetime.strptime(scan_date, "%a, %d %b %Y %H:%M:%S %Z")
                        site_summary["date"] = date_obj.replace(microsecond=0) if scan_date else None
                case "tracking":
                    site_summary["summary"]["tracking"] = results.get("tools")[0] if results.get("tools") else None
                    scan_date = results.get("date")
                    if scan_date:
                        date_obj = datetime.strptime(scan_date, "%Y-%m-%d %H:%M:%S.%f")
                        site_summary["date"] = date_obj.replace(microsecond=0) if scan_date else None
                case _:
                    continue

        if "dsfr" in available_tools:
            available_tools.add("dom")
        for tool in tools:
            if tool not in available_tools:
                print(f"  [⨯] {tool} (no data)")
                if tool == "lighthouse":
                    for key in ["performance", "accessibility", "best-practices", "seo"]:
                        site_summary["summary"][f"lighthouse_{key}"] = None
                else:
                    site_summary["summary"][tool] = None

        report.append(site_summary)

    with Path("data/report.json").open("w", encoding="utf-8") as report_file:
        json.dump(report, report_file, indent=2, ensure_ascii=False, default=str)

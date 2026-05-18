import argparse
import asyncio
import json
import logging
import re
import sys
from pathlib import Path

from ecoindex.exceptions.scraper import EcoindexScraperStatusException
from ecoindex.scraper import EcoindexScraper

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def main(domain: str) -> None:
    base_url = "https://" + domain
    scraper = EcoindexScraper(url=base_url)

    try:
        analysis_data = await scraper.get_page_analysis()
    except EcoindexScraperStatusException:
        logger.error("Unable to retrieve analysis for %s", base_url)
        return

    write_json("ecoindex", dict(analysis_data), domain)
    logger.debug("%s", analysis_data)


def clean_url(url: str) -> str:
    return re.sub(r"https?://", "", url).rstrip("/")


def write_json(filename: str, data: dict, domain: str) -> None:
    output_path = DATA_PATH / domain / f"{filename}.json"
    with Path(output_path).open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False, default=str)


DATA_PATH = Path(__file__).resolve().parents[2] / "data"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EcoIndex CLI")
    parser.add_argument("url", help="URL to crawl")
    args = parser.parse_args()

    base_domain = clean_url(args.url)

    data_dir = DATA_PATH / base_domain

    data_dir.mkdir(parents=True, exist_ok=True)

    asyncio.run(main(base_domain))

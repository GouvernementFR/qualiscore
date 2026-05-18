import argparse
import asyncio
import json
import logging
import re
import sys
from datetime import date, datetime
from pathlib import Path

from bs4 import BeautifulSoup, Tag
from camoufox.async_api import AsyncCamoufox
from constants import (
    DATA_PATH,
    DSFR_COMPONENTS,
    GDPR_SEARCH,
    SKIP_LINKS,
    TIMEOUT,
    TRACKING_TOOLS,
)
from models import DSFRResult, GDPRResult, RGAAResult, TrackingResult
from playwright.async_api import Page

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def get_screenshot(page: Page, domain: str) -> None:
    screenshot_path = DATA_PATH / domain / "screenshot.png"
    # await page.wait_for_timeout(2000)
    await page.screenshot(path=screenshot_path)


async def get_dsfr(page: Page) -> dict:
    content = await page.content()
    html = BeautifulSoup(content, "html.parser")

    header_brand = bool(html.select_one(".fr-header__brand"))

    if not header_brand:
        return DSFRResult().to_dict()

    used_components = {f"fr-{component}": bool(html.select_one(f".fr-{component}")) for component in DSFR_COMPONENTS}

    css_files = [str(link.get("href")) for link in html.find_all("a") if str(link.get("href")).endswith(".css")]
    for css_file in css_files:
        css_file_url = css_file
        if not css_file.startswith("http"):
            css_file_url = page.url.rstrip("/") + "/" + css_file.lstrip("/")

        response = await page.context.request.get(css_file_url)
        css_content = await response.text()

        version = re.findall(r"DSFR\s*v?([\d\.]+)", css_content, re.IGNORECASE)
        if version:
            version = version[0]
            break
    else:
        version = None

    if not version:
        # This is insecure and might be detected by the target website, we keep it as a fallback
        version = await page.evaluate("mw:window.dsfr?.version")

    return DSFRResult(
        header_brand=header_brand,
        version=version,
        components=used_components,
    ).to_dict()


async def get_rgaa(page: Page, base_url: str) -> dict:
    content = await page.content()
    html = BeautifulSoup(content, "html.parser")

    links = html.find_all("a")

    accessibility_elements = [link for link in links if "accessibilité" in link.text.lower()]

    skip_links = bool(html.select_one(".fr-skiplinks")) or any(t in html.text.lower() for t in SKIP_LINKS)

    if not accessibility_elements:
        return RGAAResult(skip_links=skip_links).to_dict()

    accessibility_element = accessibility_elements[0]
    if len(accessibility_elements) > 1:
        for link in accessibility_elements:
            if ":" in link.text or "-" in link.text:
                accessibility_element = link
                break

    url, mention = get_link_info(accessibility_element, base_url)

    if not url:
        return RGAAResult(skip_links=skip_links).to_dict()

    in_dsfr_footer = bool(accessibility_element.find_parent(class_="fr-footer"))

    await page.goto(url)
    try:
        await page.wait_for_load_state("networkidle", timeout=TIMEOUT)
    except Exception:
        await page.wait_for_load_state("domcontentloaded", timeout=TIMEOUT)

    rgaa_content = await page.content()
    rgaa_html = BeautifulSoup(rgaa_content, "html.parser")
    if url.endswith(".pdf"):
        rgaa_html = rgaa_html.find(id="viewer") or rgaa_html
        # TODO wait for PDF to be fully loaded (only first page is loaded at the beginning)

    cited_law = "2005-102" in rgaa_html.text or "article 47" in rgaa_html.text.lower()
    versions = re.findall(r"RGAA\s+(v|version)?\s*([\d\.]+)", rgaa_html.text, re.IGNORECASE)
    version = versions[0][1].rstrip(".") if versions and versions[0] else None
    percentages = re.findall(r"[\d\.,]+\s*%", rgaa_html.text, re.IGNORECASE)
    percentages = [p for p in percentages if float(p.replace("%", "").replace(",", ".")) <= 100]
    percentage = float(percentages[0].replace("%", "").replace(",", ".")) if percentages and percentages[0] else None
    if len(percentages) > 1:
        percentage = max(float(p.replace("%", "").replace(",", ".")) for p in percentages)
    update_dates = re.findall(r"(mise\s+[àa]\s+jour|[ée]tablie)\s+(du|le)?\s*([\d\-/]+)", rgaa_html.text, re.IGNORECASE)
    update_date = clean_date(update_dates[0][2]) if update_dates and update_dates[0] else None
    if len(update_dates) > 1:
        dates = []
        for d in update_dates:
            clean_date_str = clean_date(d[2])
            if clean_date_str:
                dates.append(clean_date_str)
        if dates:
            update_date = max(dates)

    return RGAAResult(
        url=url,
        mention=mention,
        in_dsfr_footer=in_dsfr_footer,
        skip_links=skip_links,
        cited_law=cited_law,
        rgaa_version=version,
        rgaa_percentage=percentage,
        rgaa_update_date=update_date,
    ).to_dict()


async def get_gdpr(page: Page, base_url: str) -> dict:
    content = await page.content()
    html = BeautifulSoup(content, "html.parser")

    links = html.find_all("a")

    result = GDPRResult()

    for key in ["ml", "pc", "cgu"]:
        elements = [link for link in links if any(str(t) in link.text.lower() for t in GDPR_SEARCH[key])]
        if not elements:
            continue

        url, mention = get_link_info(elements[0], base_url)
        result[f"{key}_url"] = url
        result[f"{key}_mention"] = mention

        if not url:
            continue

        await page.goto(url)
        try:
            await page.wait_for_load_state("networkidle", timeout=TIMEOUT)
        except Exception:
            await page.wait_for_load_state("domcontentloaded", timeout=TIMEOUT)

        page_content = await page.content()
        page_html = BeautifulSoup(page_content, "html.parser")
        page_text = clean_text(page_html.text.lower())

        for group in GDPR_SEARCH[f"{key}_words"]:
            for keyword in group:
                if keyword in page_text:
                    result[f"{key}_matches"].append(keyword)
                    break
            else:
                result[f"{key}_missing"].append(" (ou) ".join(group))

    return result.to_dict()


async def get_tracking(page: Page) -> dict:
    content = await page.content()

    detected_tools = set()
    for tool_name, tool_pattern in TRACKING_TOOLS.items():
        if re.search(tool_pattern, content, re.IGNORECASE):
            detected_tools.add(tool_name)

    has_tac = re.search(r"(tacjs|tarteaucitron)", content, re.IGNORECASE) is not None
    has_orejime = re.search(r"orejime", content, re.IGNORECASE) is not None

    return TrackingResult(
        available=bool(detected_tools),
        tools=list(detected_tools),
        has_tac=has_tac,
        has_orejime=has_orejime,
        date=datetime.now(),
    ).to_dict()


async def main(domain: str) -> None:
    base_url = "https://" + domain

    async with AsyncCamoufox(headless="virtual", main_world_eval=True) as browser:
        context = await browser.new_context(  # ty:ignore[unresolved-attribute]
            screen={"width": 1280, "height": 720},
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        try:
            await page.goto(base_url)
        except Exception as e:
            logger.error("Error navigating: %s", str(e).replace("\n", " "))
            return

        try:
            await page.wait_for_load_state("networkidle", timeout=TIMEOUT)
        except Exception:
            await page.wait_for_load_state("domcontentloaded", timeout=TIMEOUT)

        data_dir = DATA_PATH / domain

        data_dir.mkdir(parents=True, exist_ok=True)

        await get_screenshot(page, domain)

        dsfr_data = await get_dsfr(page)
        write_json("dsfr", dsfr_data, domain)
        logger.debug("DSFR %s", dsfr_data)

        rgaa_data = await get_rgaa(page, base_url)
        write_json("rgaa", rgaa_data, domain)
        logger.debug("RGAA %s", rgaa_data)

        gdpr_data = await get_gdpr(page, base_url)
        write_json("gdpr", gdpr_data, domain)
        logger.debug("GDPR %s", gdpr_data)

        tracking_data = await get_tracking(page)
        write_json("tracking", tracking_data, domain)
        logger.debug("Tracking %s", tracking_data)

        await context.close()


def clean_url(url: str) -> str:
    return re.sub(r"https?://", "", url).split("/")[0].lower()


def clean_text(text: str) -> str:
    return text.strip().replace(" ", " ").replace("’", "'")


def clean_date(date_str: str) -> date | None:
    try:
        day, month, year = map(int, date_str.replace("-", "/").split("/"))
        return date(year, month, day)
    except ValueError:
        return None


def get_link_info(element: Tag, base_url: str) -> tuple[str, str]:
    element_href = str(element.get("href"))
    element_text = clean_text(element.text)
    if element_href and not element_href.startswith("http"):
        return (base_url.rstrip("/") + "/" + element_href.lstrip("/"), element_text)
    return (element_href, element_text)


def write_json(filename: str, data: dict, domain: str) -> None:
    output_path = DATA_PATH / domain / f"{filename}.json"
    with Path(output_path).open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False, default=str)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DOM CLI")
    parser.add_argument("url", help="URL to crawl")
    args = parser.parse_args()

    base_domain = clean_url(args.url)

    asyncio.run(main(base_domain))

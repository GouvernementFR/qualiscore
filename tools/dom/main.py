import argparse
import asyncio
import json
import re
from datetime import date, datetime

from bs4 import BeautifulSoup, Tag
from camoufox.async_api import AsyncCamoufox
from constants import DATA_PATH, DSFR_COMPONENTS, GDPR_SEARCH, SKIP_LINKS, TIMEOUT, TRACKING_TOOLS
from playwright.async_api import Page


async def get_screenshot(page: Page, domain: str) -> None:
    await page.wait_for_timeout(2000)
    screenshot_path = DATA_PATH / domain / "screenshot.png"
    await page.screenshot(path=screenshot_path)


async def get_dsfr(page: Page):
    content = await page.content()
    html = BeautifulSoup(content, "html.parser")

    has_header_brand = bool(html.select_one(".fr-header__brand"))

    if not has_header_brand:
        return {
            "enabled": False,
            "version": None,
            "used_components": {},
        }

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

    return {
        "enabled": has_header_brand,
        "version": version,
        "used_components": used_components,
    }


async def get_a11y(page: Page, base_url: str):
    content = await page.content()
    html = BeautifulSoup(content, "html.parser")

    links = html.find_all("a")

    accessibility_elements = [link for link in links if "accessibilité" in link.text.lower()]

    skip_links = bool(html.select_one(".fr-skiplinks")) or any(t in html.text.lower() for t in SKIP_LINKS)

    if not accessibility_elements:
        return {
            "url": None,
            "mention": None,
            "in_dsfr_footer": False,
            "skip_links": skip_links,
            "cited_law": False,
            "rgaa_version": None,
            "rgaa_percentage": None,
            "rgaa_update_date": None,
        }

    accessibility_element = accessibility_elements[0]
    if len(accessibility_elements) > 1:
        for link in accessibility_elements:
            if ":" in link.text or "-" in link.text:
                accessibility_element = link
                break

    link_url, link_mention = get_link_info(accessibility_element, base_url)

    in_footer = bool(accessibility_element.find_parent(class_="fr-footer"))

    await page.goto(link_url)

    await page.wait_for_load_state("networkidle", timeout=TIMEOUT)

    a11y_content = await page.content()
    a11y_html = BeautifulSoup(a11y_content, "html.parser")

    cited_law = "2005-102" in a11y_html.text or "article 47" in a11y_html.text.lower()
    versions = re.findall(r"RGAA\s*(v|version)?\s*([\d\.]+)", a11y_html.text, re.IGNORECASE)
    version = versions[0][1].rstrip(".") if versions and versions[0] else None
    percentages = re.findall(r"[\d\.,]+\s*%", a11y_html.text, re.IGNORECASE)
    percentage = float(percentages[0].replace("%", "").replace(",", ".")) if percentages and percentages[0] else None
    if len(percentages) > 1:
        percentage = max(float(p.replace("%", "").replace(",", ".")) for p in percentages)
    update_dates = re.findall(r"(mise\s+[àa]\s+jour|[ée]tablie)\s+(du|le)?\s+([\d\-/]+)", a11y_html.text, re.IGNORECASE)
    update_date = clean_date(update_dates[0][2]) if update_dates and update_dates[0] else None
    if len(update_dates) > 1:
        dates = []
        for d in update_dates:
            clean_date_str = clean_date(d[2])
            if clean_date_str:
                dates.append(clean_date_str)
        if dates:
            update_date = max(dates)

    return {
        "url": link_url,
        "mention": link_mention,
        "in_dsfr_footer": in_footer,
        "skip_links": skip_links,
        "cited_law": cited_law,
        "rgaa_version": version,
        "rgaa_percentage": percentage,
        "rgaa_update_date": update_date,
    }


async def get_gdpr(page: Page, base_url: str):
    content = await page.content()
    html = BeautifulSoup(content, "html.parser")

    links = html.find_all("a")

    ml_elements = [link for link in links if any(t in link.text.lower() for t in GDPR_SEARCH["ml"])]  # ty:ignore[unsupported-operator]

    pc_elements = [link for link in links if any(t in link.text.lower() for t in GDPR_SEARCH["pc"])]  # ty:ignore[unsupported-operator]

    cgu_elements = [link for link in links if any(t in link.text.lower() for t in GDPR_SEARCH["cgu"])]  # ty:ignore[unsupported-operator]

    if not (ml_elements or pc_elements or cgu_elements):
        return {
            "ml_url": None,
            "ml_mention": None,
            "ml_matches": [],
            "ml_missing": [],
            "pc_url": None,
            "pc_mention": None,
            "pc_matches": [],
            "pc_missing": [],
            "cgu_url": None,
            "cgu_mention": None,
            "cgu_matches": [],
            "cgu_missing": [],
        }

    ml_link_url, ml_link_mention, ml_matches, ml_missing = None, None, [], []
    if ml_elements:
        ml_link_url, ml_link_mention = get_link_info(ml_elements[0], base_url)

        await page.goto(ml_link_url)

        await page.wait_for_load_state("networkidle", timeout=TIMEOUT)

        ml_content = await page.content()
        ml_html = BeautifulSoup(ml_content, "html.parser")

        for group in GDPR_SEARCH["ml_words"]:
            for keyword in group:
                if keyword in ml_html.text.lower():
                    ml_matches.append(keyword)
                    break
            else:
                ml_missing.append(" (ou) ".join(group))

    pc_link_url, pc_link_mention, pc_matches, pc_missing = None, None, [], []
    if pc_elements:
        pc_link_url, pc_link_mention = get_link_info(pc_elements[0], base_url)

        await page.goto(pc_link_url)

        await page.wait_for_load_state("networkidle", timeout=TIMEOUT)

        pc_content = await page.content()
        pc_html = BeautifulSoup(pc_content, "html.parser")

        for group in GDPR_SEARCH["pc_words"]:
            for keyword in group:
                if keyword in pc_html.text.lower():
                    pc_matches.append(keyword)
                    break
            else:
                pc_missing.append(" (ou) ".join(group))

    cgu_link_url, cgu_link_mention, cgu_matches, cgu_missing = None, None, [], []
    if cgu_elements:
        cgu_link_url, cgu_link_mention = get_link_info(cgu_elements[0], base_url)

        await page.goto(cgu_link_url)

        await page.wait_for_load_state("networkidle", timeout=TIMEOUT)

        cgu_content = await page.content()
        cgu_html = BeautifulSoup(cgu_content, "html.parser")

        for group in GDPR_SEARCH["cgu_words"]:
            for keyword in group:
                if keyword in cgu_html.text.lower():
                    cgu_matches.append(keyword)
                    break
            else:
                cgu_missing.append(" (ou) ".join(group))

    return {
        "ml_url": ml_link_url,
        "ml_mention": ml_link_mention,
        "ml_matches": ml_matches,
        "ml_missing": ml_missing,
        "pc_url": pc_link_url,
        "pc_mention": pc_link_mention,
        "pc_matches": pc_matches,
        "pc_missing": pc_missing,
        "cgu_url": cgu_link_url,
        "cgu_mention": cgu_link_mention,
        "cgu_matches": cgu_matches,
        "cgu_missing": cgu_missing,
    }


async def get_tracking(page: Page):
    await page.wait_for_load_state("domcontentloaded", timeout=TIMEOUT)
    content = await page.content()

    detected_tools = set()
    for tool_name, tool_pattern in TRACKING_TOOLS.items():
        if re.search(tool_pattern, content, re.IGNORECASE):
            detected_tools.add(tool_name)
    tac_services = []

    has_tac = re.search(r"(tacjs|tarteaucitron)", content, re.IGNORECASE) is not None
    has_orejime = re.search(r"orejime", content, re.IGNORECASE) is not None

    if not detected_tools and has_tac:
        # This is insecure and might be detected by the target website, we keep it as a fallback
        services = await page.evaluate("mw:window.tarteaucitron?.services")
        if services:
            tac_services = list(services.keys())
            for service in services:
                if "eulerian" in service.lower():
                    detected_tools.add("eulerian")

    return {
        "available": bool(detected_tools),
        "tools": list(detected_tools),
        "tac_services": tac_services,
        "has_tac": has_tac,
        "has_orejime": has_orejime,
        "date": datetime.now(),
    }


async def main(domain: str) -> None:
    base_url = "https://" + domain

    async with AsyncCamoufox(headless=True, main_world_eval=True) as browser:
        context = await browser.new_context(  # ty:ignore[unresolved-attribute]
            viewport={"width": 1280, "height": 720},
            device_scale_factor=2,
        )
        page = await context.new_page()

        await page.goto(base_url)

        await page.wait_for_load_state("networkidle", timeout=TIMEOUT)

        await get_screenshot(page, domain)

        dsfr_data = await get_dsfr(page)
        write_json("dsfr", dsfr_data, domain)
        print(dsfr_data)

        a11y_data = await get_a11y(page, base_url)
        write_json("a11y", a11y_data, domain)
        print(a11y_data)

        gdpr_data = await get_gdpr(page, base_url)
        write_json("gdpr", gdpr_data, domain)
        print(gdpr_data)

        tracking_data = await get_tracking(page)
        write_json("tracking", tracking_data, domain)
        print(tracking_data)

        await context.close()


def clean_url(url: str) -> str:
    return re.sub(r"https?://", "", url).rstrip("/")


def clean_date(date_str: str) -> date | None:
    try:
        day, month, year = map(int, date_str.replace("-", "/").split("/"))
        return date(year, month, day)
    except ValueError:
        return None


def get_link_info(element: Tag, base_url: str) -> tuple[str, str]:
    element_href = str(element.get("href"))
    element_text = element.text.strip().replace(" ", " ")
    if element_href and not element_href.startswith("http"):
        return (base_url.rstrip("/") + "/" + element_href.lstrip("/"), element_text)
    return (element_href, element_text)


def write_json(filename: str, data: dict, domain: str) -> None:
    output_path = DATA_PATH / domain / f"{filename}.json"
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False, default=str)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DOM CLI")
    parser.add_argument("url", help="URL to crawl")
    args = parser.parse_args()

    base_domain = clean_url(args.url)

    data_dir = DATA_PATH / base_domain

    data_dir.mkdir(parents=True, exist_ok=True)

    asyncio.run(main(base_domain))

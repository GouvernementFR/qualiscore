import argparse
import asyncio
import os
import re
from pathlib import Path

from camoufox.async_api import AsyncCamoufox
from constants import DSFR_COMPONENTS
from playwright.async_api import Page


async def get_screenshot(page: Page, url: str):
    await page.wait_for_timeout(2000)
    screenshot_path = Path(__file__).resolve().parents[2] / "data" / clean_url(url) / "screenshot.png"
    await page.screenshot(path=screenshot_path)


async def get_dsfr(page: Page):
    content = await page.content()

    has_header_brand = bool(re.search(r'class="[^"]*fr-header__brand[^"]*"', content))

    used_components = {
        f"fr-{component}": bool(re.search(rf'class="[^"]*fr-{component}[^"]*"', content))
        for component in DSFR_COMPONENTS
    }

    css_files = re.findall(r'href="([^"]*\.css)"', content)
    for css_file in css_files:
        css_file_url = css_file
        if not css_file.startswith("http"):
            css_file_url = page.url + css_file if css_file.startswith("/") else page.url + "/" + css_file

        response = await page.context.request.get(css_file_url)
        css_content = await response.text()

        version = re.findall(r"DSFR\s*v?([\d\.]+)", css_content, re.IGNORECASE)
        if version:
            version = version[0]
            break
    else:
        version = None

    return {
        "enabled": has_header_brand,
        "used_components": used_components,
        "version": version,
    }


async def main(url: str):
    async with AsyncCamoufox(headless=True) as browser:
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            device_scale_factor=2,
        )
        page = await context.new_page()

        await page.goto("https://" + url)

        await get_screenshot(page, url)

        dsfr_info = await get_dsfr(page)
        print(dsfr_info)

        await context.close()


def clean_url(url: str) -> str:
    return re.sub(r"https?://", "", url).rstrip("/")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Qualiscore CLI")
    parser.add_argument("url", help="URL to crawl")
    args = parser.parse_args()

    data_dir = Path(__file__).resolve().parents[2] / "data" / clean_url(args.url)

    os.makedirs(data_dir, exist_ok=True)

    asyncio.run(main(args.url))

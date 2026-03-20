import os
import random
import re

import nodriver as uc
from constants import DSFR_COMPONENTS, USER_AGENTS


async def get_screenshot(page: uc.Tab, url: str):
    await page.sleep(5)
    await page.save_screenshot(
        os.path.join(os.path.dirname(__file__), "..", "..", "data", clean_url(url), "screenshot.png")
    )


async def get_dsfr(page: uc.Tab):
    content = await page.get_content()

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

        await page.get(css_file_url)
        css_content = await page.get_content()

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


async def main(url: str, user_agent: str):
    headless = False
    if headless:
        browser_args = [
            "--ash-host-window-bounds=1920x1080",
            "--window-size=1920,1080",
            "--window-position=0,0",
        ]
    else:
        browser_args = [
            "--start-fullscreen",
        ]

    browser = await uc.start(
        browser_executable_path="/usr/bin/brave-browser",
        browser_args=[
            f"--user-agent={user_agent}",
            *browser_args,
        ],
        headless=headless,
    )

    page = await browser.get(url)

    await get_screenshot(page, url)

    dsfr_info = await get_dsfr(page)
    print(dsfr_info)

    await page.close()
    browser.stop()


def clean_url(url: str) -> str:
    return re.sub(r"https?://", "", url).rstrip("/")


if __name__ == "__main__":
    crawl_url = "https://www.info.gouv.fr"
    random_user_agent = random.choice(list(USER_AGENTS))

    os.makedirs(os.path.join(os.path.dirname(__file__), "..", "..", "data", clean_url(crawl_url)), exist_ok=True)

    uc.loop().run_until_complete(main(crawl_url, random_user_agent))

#!/bin/bash

function clean_url() {
	local url="$1"
	url="${url#*//}" # Remove protocol
	url="${url%%/*}" # Remove path
	echo "$url"
}

echo "Starting Lighthouse scan"

URL=$(clean_url "$1")
export CHROME_PATH=$(python -c """
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    print(p.chromium.executable_path)
""")

mkdir -p ../../data/$URL/
npx lighthouse --output-path=../../data/$URL/lighthouse.json --output json --chrome-flags="--headless --no-sandbox" "https://$URL"

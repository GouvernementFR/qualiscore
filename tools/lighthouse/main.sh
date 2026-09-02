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
npx -q lighthouse --quiet --output-path=../../data/$URL/lighthouse.json --disable-full-page-screenshot --skip-audits=screenshot-thumbnails,final-screenshot --output json --chrome-flags="--headless --no-sandbox" "https://$URL"

content=$(cat ../../data/$URL/lighthouse.json)
if [[ "$content" == *"runtimeError"* ]]; then
	rm ../../data/$URL/lighthouse.json
fi

#!/bin/bash

function clean_url() {
	local url="$1"
	url="${url#*//}" # Remove protocol
	url="${url%%/*}" # Remove path
	echo "$url"
}

echo "Starting 404 crawl"

URL=$(clean_url "$1")

cd /tmp/

OUT=$(timeout --preserve-status --foreground 600 wget -e robots=off --no-check-certificate --user-agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36" --level=5 --spider --recursive "https://$URL" 2>&1 > /dev/null || true)

cd -

mkdir -p ../../data/$URL/
if [[ "$OUT" != *"Found no broken links."* && "$OUT" != *"Remote file does not exist"* ]]; then
	echo "$OUT" | npx -q wget-parser > ../../data/$URL/errors_404.json
fi

rm -rf $URL/

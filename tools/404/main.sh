#!/bin/bash

function clean_url() {
	local url="$1"
	url="${url#*//}" # Remove protocol
	url="${url%%/*}" # Remove path
	echo "$url"
}

echo $1

URL=$(clean_url "$1")

OUT=$(timeout --preserve-status --foreground 580 wget -e robots=off --no-check-certificate --user-agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0 - dashlord" --level=5 --spider --recursive "https://$URL" 2>&1 > /dev/null || true)

mkdir -p ../../data/$URL/
echo "$OUT" | yarn -s wget-parser > ../../data/$URL/404.json

rm -rf $URL/

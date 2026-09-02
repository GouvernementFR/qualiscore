#!/bin/bash

function clean_url() {
	local url="$1"
	url="${url#*//}" # Remove protocol
	url="${url%%/*}" # Remove path
	echo "$url"
}

echo "Starting MDN HTTP Observatory scan"

URL=$(clean_url "$1")

mkdir -p ../../data/$URL/
npx -q mdn-http-observatory-scan "$URL" > ../../data/$URL/observatory.json

content=$(cat ../../data/$URL/observatory.json)
if [[ "$content" == '{"error":"The site seems to be down."}' || "$content" == '{"error":"Site did respond with an unexpected HTTP status code'* ]]; then
	rm ../../data/$URL/observatory.json
fi

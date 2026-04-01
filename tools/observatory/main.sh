#!/bin/bash

function clean_url() {
	local url="$1"
	url="${url#*//}" # Remove protocol
	url="${url%%/*}" # Remove path
	echo "$url"
}

echo $1

URL=$(clean_url "$1")

mkdir -p ../../data/$URL/
npx mdn-http-observatory-scan "$URL" > ../../data/$URL/observatory.json

#!/usr/bin/env bash
# Download missing images for TopRated/HOF pages from the Wayback Machine.
# Uses a 10-second delay between requests to avoid rate limiting.
#
# Usage: ./scripts/fetch_fms_images.sh
# Re-run safely — skips already-downloaded files.

set -euo pipefail
cd "$(dirname "$0")/.."

DELAY=${1:-10}  # seconds between requests, override with first arg
ASSETS_DIR="archive/assets"
TIMESTAMPS=(20120524222122 20120718125927 20130601 20110601)

# Collect all image URLs referenced in fms pages
echo "Scanning archive/fms/*.html for image references..."
grep -ohE '/_assets/[^"'\'' ><]+\.(jpg|gif|png|jpeg|bmp|ico)' archive/fms/*.html \
    | sort -u > /tmp/all_fms_images.txt

total=$(wc -l < /tmp/all_fms_images.txt)
echo "Found $total unique image references"

ok=0
fail=0
skip=0
i=0

while IFS= read -r url; do
    i=$((i+1))
    relpath="${url#/_assets/}"
    dest="$ASSETS_DIR/$relpath"

    # Skip if already downloaded
    if [ -f "$dest" ] && [ "$(wc -c < "$dest")" -gt 100 ]; then
        skip=$((skip+1))
        continue
    fi

    mkdir -p "$(dirname "$dest")"
    got=0

    for ts in "${TIMESTAMPS[@]}"; do
        sleep "$DELAY"
        http_code=$(curl -sL --max-time 20 -w '%{http_code}' \
            -H "User-Agent: Mozilla/5.0" \
            "https://web.archive.org/web/${ts}/http://$relpath" \
            -o "$dest" 2>/dev/null || true)

        if [ -f "$dest" ] && [ "$(wc -c < "$dest")" -gt 100 ]; then
            ok=$((ok+1))
            got=1
            echo "[$i/$total] OK   $relpath"
            break
        fi

        rm -f "$dest" 2>/dev/null

        # Back off on 429
        if [ "$http_code" = "429" ]; then
            echo "[$i/$total] 429 rate limited — sleeping 60s..."
            sleep 60
        fi
    done

    [ "$got" -eq 0 ] && fail=$((fail+1)) && echo "[$i/$total] FAIL $relpath"

done < /tmp/all_fms_images.txt

echo ""
echo "==============================="
echo "Done: $ok downloaded, $skip already had, $fail failed (of $total)"

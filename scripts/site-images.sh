#!/usr/bin/env bash
# Site screenshots: 480px copies of docs/screenshots/{home,fingersteaks,detail,map,honors}.png in docs/img/, PNG plus WebP (cwebp -q 84).
# Run after the App Store screenshots exist in docs/screenshots/, then re-run scripts/make-site.py (it reads the image sizes, and a
# screenshot without its copy here is simply left off the landing page). Until then this makes nothing and exits cleanly.
set -euo pipefail
cd "$(dirname "$0")/.."
made=0
for s in home fingersteaks detail map honors; do
  if [ ! -f "docs/screenshots/$s.png" ]; then
    echo "skip $s: no docs/screenshots/$s.png yet"
    continue
  fi
  mkdir -p docs/img
  sips -Z 1043 "docs/screenshots/$s.png" --out "docs/img/screen-$s.png" >/dev/null   # 480 x 1043 for a 1320 x 2868 capture
  if command -v cwebp >/dev/null; then cwebp -quiet -q 84 "docs/img/screen-$s.png" -o "docs/img/screen-$s.webp"; fi
  made=$((made + 1))
done
echo "made $made site screenshot(s)"
[ "$made" -gt 0 ] && ls -la docs/img || true

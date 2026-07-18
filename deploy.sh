#!/usr/bin/env bash
# Veilige deploy voor mer-register.nl (Cloudflare Pages, direct upload).
#
# WAAROM DIT SCRIPT: `wrangler pages deploy .` uploadt de HELE map incl. .env
# (zie het ponsenkaart-.env-lek 2026-07-01). Dit script deployt UITSLUITEND de
# publieke web/-assets vanuit een schone staging-map.
#   >>> Gebruik ALTIJD ./deploy.sh — nooit `wrangler pages deploy .` <<<
set -euo pipefail
cd "$(dirname "$0")"

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

# Alleen de publieke frontend-assets (geen README/.gitkeep/dotfiles).
for f in index.html MER-register.dc.html support.js mer-data.js; do
  cp "web/$f" "$STAGE"/
done

# Vangnet: weiger te deployen als er tóch een secret in de staging-map zit.
if grep -rqE "cfut_|CLOUDFLARE_API_TOKEN|MER_PROD_URL|postgres://|postgresql://" "$STAGE"; then
  echo "ABORT: mogelijke secret in staging-map — deploy afgebroken." >&2
  exit 1
fi

export CLOUDFLARE_API_TOKEN="$(grep '^CLOUDFLARE_API_TOKEN=' .env | cut -d= -f2- | tr -d '\r\n" ')"
export CLOUDFLARE_ACCOUNT_ID="$(grep '^CLOUDFLARE_ACCOUNT_ID=' .env | cut -d= -f2- | tr -d '\r\n" ')"

echo "Deploying schone staging-map naar mer-register (branch main)…"
npx wrangler pages deploy "$STAGE" --project-name=mer-register --branch=main --commit-dirty=true

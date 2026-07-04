#!/usr/bin/env bash
# churchit self-host automated installer script.
#
#   # Run the following command
#   curl -fsSL https://raw.githubusercontent.com/meichthys/churchit/version-15/deploy/setup.sh | bash

set -euo pipefail

REPO="meichthys/churchit"
# Frappe version branch. When upgrading Frappe, see the "Upgrading Frappe"
# checklist in .github/workflows/build-image.yml.
REF="${CHURCHIT_REF:-version-15}"
RAW="https://raw.githubusercontent.com/${REPO}/${REF}/deploy"
DIR="${CHURCHIT_DIR:-$HOME/churchit}"

say()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m%s\033[0m\n' "$*"; }

# 1) Docker -----------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
  say "Installing Docker (one-time)…"
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "$USER" || true
  warn "Docker installed. Log out and back in (or reboot), then run this again."
  exit 0
fi
if ! docker compose version >/dev/null 2>&1; then
  warn "The Docker Compose plugin is missing. Install Docker Desktop or the"
  warn "docker-compose-plugin package, then re-run this script."
  exit 1
fi

# 2) Download compose + proxy config ---------------------------------
say "Installing to $DIR"
mkdir -p "$DIR" && cd "$DIR"
curl -fsSL "$RAW/docker-compose.yml" -o docker-compose.yml
curl -fsSL "$RAW/Caddyfile"          -o Caddyfile

# 3) First-time configuration ----------------------------------------
if [ ! -f .env ]; then
  curl -fsSL "$RAW/.env.example" -o .env
  say "First-time setup:"
  printf '  Enter the domain name for this server — just the name, with no\n'
  printf '  "http://" or "https://" and no trailing slash (e.g. church.example.org).\n'
  printf '  Or press Enter to use the default of churchit.localhost: '
  read -r DOMAIN </dev/tty || DOMAIN=""
  DOMAIN="${DOMAIN:-churchit.localhost}"
  # Be forgiving if someone pastes a full URL: keep only the bare host name.
  DOMAIN="${DOMAIN#http://}"; DOMAIN="${DOMAIN#https://}"; DOMAIN="${DOMAIN%%/*}"
  # Web ports. Standard is 80/443 — change only if those are already used on
  # this machine (another web server, or local testing alongside other apps).
  printf '  HTTP port  (press Enter for 80): '
  read -r HTTP_PORT_IN </dev/tty || HTTP_PORT_IN=""
  HTTP_PORT_IN="${HTTP_PORT_IN:-80}"
  printf '  HTTPS port (press Enter for 443): '
  read -r HTTPS_PORT_IN </dev/tty || HTTPS_PORT_IN=""
  HTTPS_PORT_IN="${HTTPS_PORT_IN:-443}"
  DBP="$(openssl rand -hex 16 2>/dev/null  || echo "db${RANDOM}${RANDOM}")"
  ADMP="$(openssl rand -hex 10 2>/dev/null || echo "admin${RANDOM}")"
  # Local *.localhost -> plain HTTP (no cert warning). Real domain -> auto HTTPS.
  case "$DOMAIN" in
    localhost|*.localhost) CADDY="http://${DOMAIN}" ;;
    *)                     CADDY="${DOMAIN}" ;;
  esac
  sed -i.bak \
    -e "s|^SITE_NAME=.*|SITE_NAME=${DOMAIN}|" \
    -e "s|^CADDY_ADDRESS=.*|CADDY_ADDRESS=${CADDY}|" \
    -e "s|^HTTP_PORT=.*|HTTP_PORT=${HTTP_PORT_IN}|" \
    -e "s|^HTTPS_PORT=.*|HTTPS_PORT=${HTTPS_PORT_IN}|" \
    -e "s|^DB_ROOT_PASSWORD=.*|DB_ROOT_PASSWORD=${DBP}|" \
    -e "s|^ADMIN_PASSWORD=.*|ADMIN_PASSWORD=${ADMP}|" .env
  rm -f .env.bak
fi

# 4) Launch -----------------------------------------------------------
say "Pulling images and starting up (first run downloads ~1–2 GB)…"
docker compose pull
docker compose up -d

# 5) Wait for site creation + migrations to finish -------------------
say "Setting up your site (database + migrations) — a couple of minutes…"
docker compose wait migrate >/dev/null 2>&1 || true

# 6) Summary ----------------------------------------------------------
# shellcheck disable=SC1091
set -a; . ./.env; set +a
case "${SITE_NAME}" in
  localhost|*.localhost) SCHEME="http" ;;
  *)                     SCHEME="https" ;;
esac
PORT=""
if [ "$SCHEME" = "http"  ] && [ "${HTTP_PORT:-80}"   != "80"  ]; then PORT=":${HTTP_PORT}"; fi
if [ "$SCHEME" = "https" ] && [ "${HTTPS_PORT:-443}" != "443" ]; then PORT=":${HTTPS_PORT}"; fi
say "All done!  🎉"
echo "   Address:  ${SCHEME}://${SITE_NAME}${PORT}"
echo "   Login:    Administrator"
echo "   Password: ${ADMIN_PASSWORD}"
echo
echo "   Settings & passwords are saved in: ${DIR}/.env"
echo "   Stop:     (cd ${DIR} && docker compose down)"
echo "   Update:   (cd ${DIR} && docker compose pull && docker compose up -d)"

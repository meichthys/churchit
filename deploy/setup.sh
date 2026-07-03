#!/usr/bin/env bash
# churchit self-host installer.
#
#   curl -fsSL https://raw.githubusercontent.com/meichthys/churchit/version-15/deploy/setup.sh -o setup.sh
#   cat setup.sh      # read it before running (recommended)
#   bash setup.sh
#
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
  printf '  Domain name for this server\n'
  printf '  (press Enter for a local test at http://churchit.localhost): '
  read -r DOMAIN </dev/tty || DOMAIN=""
  DOMAIN="${DOMAIN:-churchit.localhost}"
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
say "All done!  🎉"
echo "   Address:  ${SCHEME}://${SITE_NAME}"
echo "   Login:    Administrator"
echo "   Password: ${ADMIN_PASSWORD}"
echo
echo "   Settings & passwords are saved in: ${DIR}/.env"
echo "   Stop:     (cd ${DIR} && docker compose down)"
echo "   Update:   (cd ${DIR} && docker compose pull && docker compose up -d)"

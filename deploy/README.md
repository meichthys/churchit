# Self-hosting churchit

This is the free (and recommended) way to run Churchit on your own hardware.

It runs anywhere Docker runs (which includes Linux, Windows, or macOS).

Disclaimer: If you plan to make Churchit accessible from the internet, you will
            need some additional 'IT knowledge'. Make sure that
            you understand the security implications, and that your host machine is
            up to date with the latest security patches. If you are unsure about
            these things, it may be best to host Churchit on Frappe Cloud for a
            nominal fee (See the main Churchit Readme for more details on this.)

Common requirements:
- A machine that can be left running when Churchit is needed.
  - Any spare computer should work (usually 4GB+ ram is recommended)
- Ports **80** and **443** should be free on the machine.
- If using a real domain: a DNS **A record** pointing at the machine's public
  IP (needed for the automatic HTTPS certificate). For a local test you don't
  need a domain — the setup defaults to `http://churchit.localhost`.

---
## One-Liner setup scripts

To make the setup as easy as possible, we have one-liner setup scripts you can run
to pre-configure Churchit with default settings.

### Windows

1. Install **Docker Desktop for Windows** and reboot:
   https://www.docker.com/products/docker-desktop/
   (The installer enables WSL2 for you in the background.)
2. Download this `deploy` folder and unzip it.
3. Double-click **`Start Churchit.bat`**.

It downloads everything, creates the site, and opens `http://churchit.localhost`
in your browser. Your `Administrator` password is shown at the end and saved in
the `.env` file next to the script.

To start it again later, just double-click `Start Churchit.bat` again. On these
later runs it asks whether to **[1] just start** (keep your current version) or
**[2] start and update** to the latest — so a normal restart never changes your
version unless you choose to update. (Pressing Enter picks "just start".)

### macOS

Install **Docker Desktop for Mac**, then in Terminal run the same one command as
Linux below.

### Linux (Recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/meichthys/churchit/version-15/deploy/setup.sh -o setup.sh
bash setup.sh
```

The script installs Docker if it's missing, downloads the churchit compose files,
asks for your domain (press Enter to use `churchit.localhost` on your local machine),
generates strong passwords, and starts everything.

The first run will download ~1–2 GB of data.

When it finishes it prints your address and the `Administrator` password
(also saved in `~/churchit/.env`).

> **For a real, always-on church server**, a cheap Linux mini-PC or VPS are
> good options. Windows/macOS with Docker Desktop is good for trying it out, but
> remember that Docker Desktop must stay running for the site to be up.

## Everyday commands

Run these from `~/churchit`:

```bash
docker compose down                       # stop (data is saved)
docker compose up -d                      # start
docker compose pull && docker compose up -d   # update to the latest image
docker compose logs -f create-site        # watch first-time site creation progress
docker compose logs -f migrate            # watch upgrades / migrations
```

**To Update, run: `docker compose pull && docker compose up -d`.**
Upgrades add any newly-added dependencies, with no need for manual frappe `bench` commands.

## What's in this folder

| File | Purpose |
|---|---|
| `Start Churchit.bat` | Windows: double-click to start (runs `start.ps1`). |
| `start.ps1` | Windows launcher logic (PowerShell). |
| `setup.sh` | Linux/macOS one-command installer. |
| `docker-compose.yml` | The full docker stack: app, workers, MariaDB, Redis, Caddy. |
| `Caddyfile` | Reverse proxy + automatic HTTPS. |
| `.env.example` | Settings template (domain, passwords, image tag). |
| `apps.json` | App list baked into the image (frappe churchit, and dependencies). |

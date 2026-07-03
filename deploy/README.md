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

## Making Churchit reachable from the internet

By default Churchit runs locally (`http://churchit.localhost`). To let people
reach it from anywhere with a real web address and a trusted HTTPS certificate,
you need three things: a **domain name**, **DNS** pointing at your internet
connection, and your **router forwarding** web traffic to the host machine.
Caddy can then fetches a free HTTPS certificate automatically.

> ⚠️ Exposing anything to the internet has security implications (see the
> disclaimer at the top). Use a strong `Administrator` password, keep the host
> patched, and take regular backups. If this feels like too much, hosting on
> Frappe Cloud may be a better option for you.

**1. Get a domain name.** Register one (e.g. `yourchurchname.org`) with a domain
registrar, or use a subdomain you already control (e.g. `churchit.yourchurchname.org`).

**2. Run setup with that domain — and keep ports 80/443.** At the setup prompts,
enter your domain (not `churchit.localhost`) and press Enter for the default
ports. Public HTTPS **requires ports 80 and 443**: Let's Encrypt validates over
port 80, and browsers expect 443. (The custom-port option is only for local or
behind-another-proxy setups.)

**3. Point DNS at your connection.** In your domain's DNS settings, add an
**A record** for your domain pointing to your **public IP address**:

```
Type: A    Name: @ (or your subdomain)    Value: <your public IP>
```

You can find your public IP address by running `curl -4 ifconfig.me` on the host
(or search online for "what is my IP"). If your public IP changes over time
(most home connections do), you will need to use **Dynamic DNS (DDNS)** so the DNS
record updates itself each time your public ip address changes. Many registrars offer
DDNS services, but if not, you can use a free service like DuckDNS or Cloudflare.

**4. Forward ports on your router.** In your router's admin page, forward inbound
**TCP 80 and 443** to the host machine's LAN address:

```
External 80  ->  <host LAN IP>:80
External 443 ->  <host LAN IP>:443
```

Give the host a **reserved/static LAN IP** first (in the router's DHCP settings)
so the forward doesn't break after a reboot.

**5. Allow 80/443 through the host firewall.**

```bash
sudo ufw allow 80,443/tcp     # Linux (ufw)
```

On Windows, Docker Desktop usually prompts to allow this the first time.

**6. Test the connection from outside your network.**

### Can't open ports? (CGNAT, restrictive ISP, or you'd rather not)

Some connections (many residential/mobile/fibre plans) put you behind **CGNAT**, where port
forwarding can't work because you don't have your own public IP. Two options that
need **no open ports**:

- **A tunnel** — e.g. **Cloudflare Tunnel** (`cloudflared`) or **Tailscale
  Funnel**. These connect *out* from the host and expose it publicly, handling
  HTTPS for you. Run Churchit locally (keep the `churchit.localhost` / `http://`
  address) and let the tunnel front it. Setting this up is outside the scope of this tutorial.
- **Frappe Cloud**: See the project Readme for more details.

### Troubleshooting

- **"Not secure" / no certificate:** DNS isn't resolving to your IP yet, or port
  80 isn't reachable from outside. Check that `nslookup your-domain` returns your
  public IP and that port 80 is forwarded.
- **Works on your network but not from outside:** Possibly **CGNAT** - you
  may not have a public IP. Use a tunnel (above), or Frappe Cloud.
- **Certificate keeps failing:** make sure `HTTP_PORT`/`HTTPS_PORT` are `80`/`443`
  (not custom) - Let's Encrypt won't validate on other ports.

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

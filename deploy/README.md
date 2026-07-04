# Hosting Churchit on Frappe Cloud (Coming Soon)

The easiest (but not free) way to get a working Frappe environment is to use [Frappe Cloud](https://frappe.io/cloud). For a few dollars per month you can run an instance in the cloud. You get your choice of support options and shouldn't need to worry about data loss yourself.

Note: With this option, the money you pay to FrappeCloud is not received by maintainers of this 'Church' app. - We offer the 'Church' software for free, but you pay the cloud hosting costs to [Frappe](https://frappe.io/).

Additional details on this hosting method will become available in the near future.

# Self-hosting churchit

Self-hosting Churchit is the free way to run Churchit on your own hardware, but does require some technical expertise.

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

### Linux (Recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/meichthys/churchit/version-15/deploy/setup.sh | bash
```

The script installs Docker if it's missing, downloads the churchit compose files,
asks for your domain (press Enter to use `churchit.localhost` on your local machine),
generates strong passwords, and starts everything.

The first run will download ~1–2 GB of data.

When it finishes it prints your site address. Log in as `Administrator`. Your initial password is saved in `~/churchit/.env` — see [Logging in](#logging-in) below. It is HIGHLY recommended to change the Administrator password after first logging in.

> **For a real, always-on church server**, a cheap Linux mini-PC or VPS are
> good options. Windows/macOS with Docker Desktop is good for trying it out, but
> remember that Docker Desktop must stay running for the site to be up.

### Windows (via WSL)

On Windows, Churchit runs inside **WSL** (Windows Subsystem for Linux):

1. Install Docker Desktop for Windows and reboot:
   https://www.docker.com/products/docker-desktop/
2. Open PowerShell and run `wsl --install`:
   Reboot if asked, then set the username/password it
   prompts for. If WSL is already present on your system, use `wsl --install -d Ubuntu`.
3. In Docker Desktop → Settings → Resources → WSL Integration, confirm Ubuntu
   is enabled (it should be enabled by default).
4. Open **Ubuntu** from the Start menu and run the 'curl' command form the `Linux` section above.

The downloaded files, `docker compose` commands, and
the `~/churchit/.env` that holds your password all live inside WSL (Ubuntu).

### macOS

Install '[Docker Desktop for Mac](https://docs.docker.com/desktop/setup/install/mac-install/)',
then in Terminal run the 'curl' command in the 'Linux' section above.


## Logging in

- **Username:** `Administrator`
- **Initial password:** the `ADMIN_PASSWORD` value in `~/churchit/.env`. Show it with:

  ```bash
  grep ADMIN_PASSWORD ~/churchit/.env
  ```

After your first login, change it to something memorable from the web UI
(top-right avatar → **My Settings** → set a new password). Editing `ADMIN_PASSWORD`
in `.env` afterward has **no effect** — that value is only used when the site is
first created.

**Forgot the password?** Reset it any time (replace `<your-site>` with the
`SITE_NAME` from `.env`, e.g. `churchit.localhost`):

```bash
cd ~/churchit
docker compose exec backend bench --site <your-site> set-admin-password '<new-password>'
```

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

## Uninstall / start fresh

In case something went wrong during the initial setup, or you want to start fresh
you can run the commands below.

⚠️ Warning: This permanently deletes the site, database, and uploaded files.

**Linux / macOS / Windows** (on Windows, run these in your **Ubuntu / WSL** terminal):

```bash
cd ~/churchit
docker compose down -v     # stop & remove containers, network, and ALL data
cd ~ && rm -rf churchit    # remove the config folder (.env, compose files)
```

Be sure to run ` docker compose down -v` **before** deleting the folder.
To also remove the downloaded docker images, you can run `docker image prune -a`

## What's in this folder

| File | Purpose |
|---|---|
| `setup.sh` | One-command installer for Linux, macOS, and Windows (via WSL). |
| `docker-compose.yml` | The full docker stack: app, workers, MariaDB, Redis, Caddy. |
| `Caddyfile` | Reverse proxy + automatic HTTPS. |
| `.env.example` | Settings template (domain, passwords, image tag). |
| `apps.json` | App list baked into the image (frappe churchit, and dependencies). |

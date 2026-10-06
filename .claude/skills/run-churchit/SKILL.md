---
name: run-churchit
description: Run, drive, test and screenshot the churchit Frappe app on the local pilot dev bench (churchit.localhost:8000). Use when asked to start or check the churchit site, open a desk or portal page, click through a form, take a screenshot, confirm a change works in the real app, run churchit tests, migrate, or call churchit Python code directly.
---

Churchit is a Frappe app inside the pilot bench `dev`. It has no server of its own. The site
`churchit.localhost` is served at `http://churchit.localhost:8000` by a long-running pilot bench
that belongs to the user. Drive the UI with `.claude/skills/run-churchit/driver.py`, a headless
Playwright script that reads commands from stdin. Drive Python with `pilot -b dev frappe`; `bench`
is not on PATH.

All paths are relative to the app directory, `/home/matt/pilot/benches/dev/apps/churchit`.

## Prerequisites

`uv` and `pilot` are on PATH. Playwright 1.63.0 matches the cached Chromium build. Do this once per
machine; it takes under a second when the browser is already cached:

```bash
uvx --from playwright==1.63.0 playwright install chromium
```

## Check the site is up

```bash
curl -s http://churchit.localhost:8000/api/method/ping    # {"message":"pong"}
```

If this fails, the bench is down. It is the user's bench, so ask before you start it. `pilot start`
runs in the foreground and first stops any stale runner (`pilot/core/bench/runtime.py`). This skill
has not tested it.

## Run (agent path): the driver

```bash
uv run .claude/skills/run-churchit/driver.py <<'EOF'
login mary.johnson@example.com
nav /desk/rolodex?view=people
shot rolodex
errors
EOF
```

Each run is a fresh browser: log in first. Screenshots go to `/tmp/churchit-shots/<name>.png`. Read
them with the Read tool. The first command that fails saves `failed.png`, prints the errors and exits 1.

| command | what it does |
|---|---|
| `login <user> [password]` | API login. Password defaults to `admin` for Administrator, else the email |
| `nav <path>` | Go to the path, wait for network idle, hide Frappe's onboarding panel |
| `wait <selector>` | Wait until the selector is visible |
| `wait-url <glob>` | Wait for the URL, e.g. `**/desk/person/PRSN-*` after a save |
| `click <selector>` / `fill <selector> <text>` / `press <key>` | Input (quote arguments that have spaces) |
| `text <selector>` | Print the inner text |
| `eval <js>` | Run the rest of the line as JS and print it as JSON. A promise is awaited |
| `url` | Print the current URL |
| `viewport <width> <height>` | Resize the window, for taller desk screenshots |
| `sleep <ms>` | Fixed wait. Use only when there is nothing to wait for |
| `shot [name]` | Save a screenshot |
| `errors` | Print console errors, page errors and every HTTP response >= 400 |

Flags: `--device mobile` (390×844), `--theme dark` (portal only, see Gotchas), `--url <site>`, `--out <dir>`.

**Logins** (sample data, password = email): `mary.johnson@example.com` (Church Manager, desk),
`james.wilson@example.com` (Church User, portal only), `Administrator` / `admin`.

Desk form: create a record, save it, check it, then delete it:

```bash
uv run .claude/skills/run-churchit/driver.py <<'EOF'
login Administrator
nav /desk/person/new
fill "[data-fieldname=first_name] input" Driver
fill "[data-fieldname=last_name] input" Smoketest
press Control+s
wait-url **/desk/person/PRSN-*
eval cur_frm.doc.name + " | " + cur_frm.doc.full_name + " | church=" + cur_frm.doc.church
shot person-saved
eval frappe.xcall("frappe.client.delete", {doctype: "Person", name: cur_frm.doc.name})
errors
EOF
```

Portal page as a member, on a phone, in dark mode:

```bash
uv run .claude/skills/run-churchit/driver.py --device mobile --theme dark <<'EOF'
login james.wilson@example.com
nav /attendance
text main
shot attendance-mobile-dark
errors
EOF
```

## Direct invocation (Python, no browser)

```bash
pilot -b dev frappe --site churchit.localhost execute frappe.client.get_count --kwargs '{"doctype": "Person"}'
printf 'from churchit.church_scope import is_people_directory_private\nprint(is_people_directory_private())\n' \
  | pilot -b dev frappe --site churchit.localhost console
pilot -b dev frappe --site churchit.localhost migrate     # after doctype, fixture or patch changes (~11 s)
```

REST with a cookie jar. Use `-g` when the URL has `[`:

```bash
jar=$(mktemp)
curl -s -c "$jar" -X POST http://churchit.localhost:8000/api/method/login -d usr=Administrator -d pwd=admin
curl -sg -b "$jar" 'http://churchit.localhost:8000/api/resource/Person?filters=[["last_name","=","Smoketest"]]'
```

## Test

```bash
pilot -b dev frappe --site churchit.localhost run-tests --module churchit.tests.test_www_attendance
```

This runs 11 tests in about 3 s. The exit code is non-zero on failure. Run modules one at a time. A
full `run-tests --app churchit` run commits to the dev site: it re-creates the sample data and leaves
multi-church switched off.

## Gotchas

- **`wait_for_load_state` returns at once after the first load.** A "wait for idle" after a click
  waits for nothing. After a save, use `wait-url`. After other actions, use `wait <selector>`.
- **The desk scrolls `.main-section`, not the page.** `full_page` screenshots stay at the window
  height. Run `viewport 1280 2000` before `nav` to see lower content.
- **`--theme` does not change the desk.** The desk uses each user's saved theme: Administrator is
  dark, Mary is light. `--theme` only sets `prefers-color-scheme` for portal and website pages. To
  force the desk: `eval document.documentElement.dataset.theme = "dark"`.
- **`errors` on website and portal pages always shows**
  `http 500: GET .../files/website_theme/frappe/public/css/fonts/inter/inter.css`. The compiled
  Website Theme keeps a relative `@import` of Inter. This is a known issue, not your change.
- **Console messages give a status but no URL.** That is why the driver also records failed responses.
- **Portal pages have no `<h1>`.** `text h1` times out. Use `text main`.
- **`execute` prints nothing for a falsy result.** A count of 0 and `[]` both look like no output.
- **Writes in a piped `console` roll back** unless the script calls `frappe.db.commit()`.
- **The desk is at `/desk/...`, not `/app/...`.**
- **Delete what you create.** Demo records that link to sample data make
  `churchit.tests.test_sample_data` fail with `LinkValidationError`.
- **No asset build for churchit.** `sites/assets/churchit` is a symlink to `churchit/public` and
  `app_include_js` files are not bundled. JS and CSS edits show on the next `nav`, because each run
  is a fresh browser with no cache. `bench.toml` sets `reload_python = true` for Python.

## Troubleshooting

- **`TimeoutError: Locator...: Timeout 30000ms exceeded`**: nothing matched the selector. Open
  `/tmp/churchit-shots/failed.png` to see the page.
- **`curl` exits with code 3 and prints nothing**: the URL has `[` and curl read it as a glob. Add `-g`.
- **`BEWARE: your OS is not officially supported by Playwright`**: harmless on Arch. It uses the
  ubuntu24.04 fallback build.

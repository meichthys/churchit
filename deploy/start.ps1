# churchit - Windows launcher (PowerShell).
#
# Don't run this directly - double-click "Start Churchit.bat", which launches
# this with the right settings. Requires Docker Desktop:
#   https://www.docker.com/products/docker-desktop/

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

function Info($m) { Write-Host "==> $m" -ForegroundColor Cyan }
function Warn($m) { Write-Host $m -ForegroundColor Yellow }

# 1) Is Docker installed? -----------------------------------------------
try { docker version *> $null }
catch {
  Warn "Docker Desktop does not appear to be installed."
  Warn "Opening the download page - install it, reboot, then run this again."
  Start-Process "https://www.docker.com/products/docker-desktop/"
  return
}

# 2) Is the Docker engine running? --------------------------------------
try { docker info *> $null }
catch {
  Warn "Docker Desktop is installed but not running yet."
  Warn "Start Docker Desktop, wait until it shows 'Running', then run this again."
  return
}

# 3) First-time configuration -------------------------------------------
$firstRun = -not (Test-Path ".env")
if ($firstRun) {
  Info "First-time setup:"
  Write-Host "  Domain name for this server"
  $domain = Read-Host "  (press Enter for a local test at http://churchit.localhost)"
  if ([string]::IsNullOrWhiteSpace($domain)) { $domain = "churchit.localhost" }

  # Local *.localhost -> plain HTTP (no cert warning). Real domain -> auto HTTPS.
  if ($domain -eq "localhost" -or $domain -like "*.localhost") {
    $caddy = "http://$domain"
  } else {
    $caddy = $domain
  }

  $db    = [guid]::NewGuid().ToString('N')                    # 32 hex chars
  $admin = [guid]::NewGuid().ToString('N').Substring(0, 20)   # 20 hex chars
  (Get-Content ".env.example") | ForEach-Object {
    $_ -replace '^SITE_NAME=.*',        "SITE_NAME=$domain" `
       -replace '^CADDY_ADDRESS=.*',    "CADDY_ADDRESS=$caddy" `
       -replace '^DB_ROOT_PASSWORD=.*', "DB_ROOT_PASSWORD=$db" `
       -replace '^ADMIN_PASSWORD=.*',   "ADMIN_PASSWORD=$admin"
  } | Set-Content ".env"
}

# 4) Optionally update, then start --------------------------------------
if ($firstRun) {
  Info "Downloading churchit (first run, ~1-2 GB)..."
  docker compose pull
} else {
  Write-Host ""
  Write-Host "  [1] Just start  (keep the current version)"
  Write-Host "  [2] Start and update to the latest version"
  $choice = Read-Host "  Choose 1 or 2 (Enter = 1)"
  if ($choice.Trim() -eq '2') {
    Info "Updating to the latest version..."
    docker compose pull
  }
}
Info "Starting up..."
docker compose up -d

# 5) Wait for site creation + migrations to finish ----------------------
Info "Setting up your site (database + migrations) - a couple of minutes..."
try { docker compose wait migrate *> $null } catch { }

# 6) Show the result and open it ----------------------------------------
$envmap = @{}
Get-Content ".env" | ForEach-Object {
  if ($_ -match '^\s*([^#][^=]*)=(.*)$') { $envmap[$matches[1].Trim()] = $matches[2] }
}
$site  = $envmap['SITE_NAME']
$admin = $envmap['ADMIN_PASSWORD']
if ($site -eq "localhost" -or $site -like "*.localhost") { $scheme = "http" } else { $scheme = "https" }
$addr = "${scheme}://${site}"

Info "All done!"
Write-Host "   Address:  $addr"
Write-Host "   Login:    Administrator"
Write-Host "   Password: $admin"
Write-Host ""
Write-Host "   Settings and password are saved in the .env file next to this script."
Write-Host "   To start or update later, double-click 'Start Churchit.bat' again."
Start-Process $addr

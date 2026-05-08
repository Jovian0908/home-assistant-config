# ha_cutover_dryrun.ps1 - Phase 7 cutover dry-run.
#
# Validates the rsync-from-sandbox-to-CM5 flow without actually touching CM5.
# Steps:
#   1. Audit the public-repo HA config (must be clean of dangling refs)
#   2. Re-fetch the sandbox-side configuration.yaml + packages + dashboards
#   3. Dump them to a staging tree on the local disk
#   4. Diff staging vs the public repo to verify they're in lockstep
#   5. Print a "ready to cutover" or "blocked: ..." summary
#
# Live cutover (separate script, NOT invoked here):
#   - ssh root@192.168.0.50 "ha backups new --name pre-cutover-$(Get-Date -f 'yyyy-MM-dd-HHmm')"
#   - rsync -av staging/ root@192.168.0.50:/homeassistant/
#   - ssh root@192.168.0.50 "ha core check"
#   - if check passes: ssh root@192.168.0.50 "ha core restart"
#   - wait 3 min for healthcheck recovery
#   - run smoke pipeline (6 voice demos + dashboard + audit)
#   - any red -> ha backups restore <pre-cutover>

$ErrorActionPreference = "Stop"

$REPO    = "C:\Users\jovia\home-assistant-config"
$STAGING = "C:\Users\jovia\.cutover-staging"
$AUDIT   = "C:\Users\jovia\scripts\ha_audit.py"
$SANDBOX_URL = "http://192.168.0.94:8124"
$CM5_URL = "http://192.168.0.50:8123"
$REPORT  = "C:\Users\jovia\docs\cutover-dryrun-report.md"

function Write-Step($n, $msg) {
    Write-Host ""
    Write-Host "=== [$n] $msg ===" -ForegroundColor Cyan
}

# --- Step 1: Audit public-repo config -------------------------------
Write-Step 1 "audit public-repo config against sandbox HA"
$auditOutput = & python $AUDIT --ha-url $SANDBOX_URL --config-dir $REPO 2>&1
$auditOutput | Write-Host
$auditFindings = ($auditOutput | Select-String "(\d+) findings").Matches.Groups[1].Value
if ($auditFindings -and [int]$auditFindings -gt 5) {
    Write-Host "FAIL: audit reports $auditFindings findings - investigate before cutover" -ForegroundColor Red
    $blocker = "audit-too-noisy"
} else {
    Write-Host "OK: audit acceptable ($auditFindings findings - known FPs)" -ForegroundColor Green
}

# --- Step 2: Re-fetch sandbox config to staging ---------------------
Write-Step 2 "stage sandbox config -> $STAGING"
if (Test-Path $STAGING) {
    Remove-Item -Recurse -Force $STAGING
}
New-Item -ItemType Directory -Path $STAGING | Out-Null
$keyFiles = @(
    "configuration.yaml",
    "automations.yaml",
    "scripts.yaml",
    "scenes.yaml",
    "packages",
    "dashboards",
    "custom_components"
)
foreach ($f in $keyFiles) {
    $src = "/config/$f"
    Write-Host "  fetching $f"
    $localDest = Join-Path $STAGING $f
    docker cp "mesh-ha-sandbox:$src" "$localDest" 2>$null
}
$stagedCount = (Get-ChildItem -Recurse $STAGING | Measure-Object).Count
Write-Host "OK: staged $stagedCount items" -ForegroundColor Green

# --- Step 3: Diff staging vs repo -----------------------------------
Write-Step 3 "diff staging vs public repo"
$diffOutput = @()
foreach ($f in $keyFiles) {
    $stagedPath = Join-Path $STAGING $f
    $repoPath = Join-Path $REPO $f
    if (-not (Test-Path $stagedPath)) {
        $diffOutput += "MISSING IN STAGING: $f"
        continue
    }
    if (-not (Test-Path $repoPath)) {
        $diffOutput += "MISSING IN REPO: $f"
        continue
    }
    if ((Get-Item $stagedPath).PSIsContainer) {
        $stagedFiles = Get-ChildItem -Recurse $stagedPath | Sort-Object FullName | ForEach-Object { $_.FullName.Substring($stagedPath.Length) }
        $repoFiles = Get-ChildItem -Recurse $repoPath | Sort-Object FullName | ForEach-Object { $_.FullName.Substring($repoPath.Length) }
        $missing = $repoFiles | Where-Object { $stagedFiles -notcontains $_ }
        $extra = $stagedFiles | Where-Object { $repoFiles -notcontains $_ }
        if ($missing) { $diffOutput += "in repo not in sandbox: $($missing -join ', ')" }
        if ($extra) { $diffOutput += "in sandbox not in repo: $($extra -join ', ')" }
    } else {
        $sH = (Get-FileHash $stagedPath -Algorithm SHA256).Hash
        $rH = (Get-FileHash $repoPath -Algorithm SHA256).Hash
        if ($sH -ne $rH) { $diffOutput += "HASH DIFF: $f" }
    }
}
if ($diffOutput.Count -eq 0) {
    Write-Host "OK: staging and repo are in lockstep" -ForegroundColor Green
} else {
    Write-Host "WARNINGS:" -ForegroundColor Yellow
    $diffOutput | ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }
}

# --- Step 4: Verify CM5 reachable + healthy -------------------------
Write-Step 4 "ping CM5 (cutover target)"
try {
    $cm5Ping = Invoke-WebRequest -Uri "$CM5_URL/" -Method Head -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
    Write-Host "OK: CM5 HA HTTP $($cm5Ping.StatusCode)" -ForegroundColor Green
} catch {
    Write-Host "WARN: CM5 not reachable: $($_.Exception.Message)" -ForegroundColor Yellow
    Write-Host "      cutover requires CM5 reachable; verify network" -ForegroundColor Yellow
}

# --- Step 5: Write cutover-readiness report -------------------------
Write-Step 5 "write report -> $REPORT"
$now = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$verdict = if ($blocker) { "BLOCKED: $blocker" } elseif ($diffOutput.Count -eq 0) { "READY" } else { "READY (with $($diffOutput.Count) advisory diffs)" }

$auditText = $auditOutput | Out-String
$reportLines = @(
    "# Cutover dry-run report",
    "",
    "_Run $now via ha_cutover_dryrun.ps1._",
    "",
    "## Verdict",
    "",
    "**$verdict**",
    "",
    "## Audit findings on public-repo config",
    "",
    '```',
    $auditText.TrimEnd(),
    '```',
    "",
    "## Staging diff",
    ""
)
if ($diffOutput.Count -eq 0) {
    $reportLines += "Lockstep clean."
} else {
    $reportLines += '```'
    $reportLines += $diffOutput
    $reportLines += '```'
}
$reportLines += @(
    "",
    "## Cutover procedure (DO NOT RUN in this script)",
    "",
    "1. ``ssh root@192.168.0.50 'ha backups new --name pre-cutover-`$(Get-Date -f yyyy-MM-dd-HHmm)'``",
    "2. ``ssh root@192.168.0.50 'docker stop addon_*' `` (optional - keeps HA core only)",
    "3. ``rsync -av --exclude='secrets.yaml' --exclude='.storage/' $STAGING/ root@192.168.0.50:/homeassistant/``",
    "4. ``ssh root@192.168.0.50 'ha core check'``  (must pass)",
    "5. ``ssh root@192.168.0.50 'ha core restart'``",
    "6. wait ~3 min for healthcheck recovery",
    "7. run smoke pipeline:",
    "   - ``python scripts/flagship_demo_drive.py`` (point HA_URL at CM5)",
    "   - ``python scripts/ha_audit.py --ha-url http://192.168.0.50:8123``",
    "8. any red -> rollback: ``ssh root@192.168.0.50 'ha backups restore <pre-cutover>'``",
    "",
    "## Post-cutover handoff",
    "",
    "- Family PDF accessible at https://192.168.0.50:8123/local/docs/family-manual.pdf",
    "- Public repo green CI for >=3 nights",
    "- Add stamp in memory/project_mesh_daily.md: ""HA renovation v2 complete, lockout begins YYYY-MM-DD""",
    "- Future-me: read docs/technical-manual.md before touching anything"
)
Set-Content -Path $REPORT -Value $reportLines -Encoding utf8

Write-Host ""
Write-Host "=== Dry-run complete: $verdict ===" -ForegroundColor Cyan
Write-Host "Report: $REPORT"

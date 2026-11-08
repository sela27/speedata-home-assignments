<#
.SYNOPSIS
    Runs the k6 load generator against SkyWatch, for the dashboard and HPA demo.
.DESCRIPTION
    Runs scripts/load.js in a pinned grafana/k6 container. For 5 minutes k6 asks
    the frontend's Ingress for pages, 10 cities in turn, at up to 45 pages a
    second. Meanwhile the HPA scales the backend from 2 replicas to 3, and back
    to 2 about 5 minutes after the load ends. k6 prints a summary at the end,
    also when Ctrl+C stops it early (it then exits with code 105). Run it after
    2-cluster, once ArgoCD has synced SkyWatch. Does not need elevation.
    Each backend pod keeps a Weather report for 10 minutes, so reports left
    from a recent run can expire together mid-run. That only makes those
    cities' pages wait a few seconds for Open-Meteo.
#>

$ErrorActionPreference = 'Stop'

$image  = 'grafana/k6:2.3.0'
$loadJs = Join-Path $PSScriptRoot 'load.js'

# A failing program does not stop PowerShell, even with 'Stop' above, so check its exit code.
function Invoke-Docker {
    # docker prints its pull progress on stderr, and k6 its log lines (k6's progress and
    # summary go to stdout). That is not a failure; the exit code is.
    # 'Continue' keeps PowerShell from stopping on that stderr text.
    $ErrorActionPreference = 'Continue'
    & docker @args
    if ($LASTEXITCODE -ne 0) { throw "'docker $args' failed with exit code $LASTEXITCODE." }
}

# 1. Prerequisites: Docker.
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'docker is not on PATH. Install Docker Desktop, then open a new PowerShell window.'
}

# 2. The load. The container's name keeps a second load from starting while one runs.
# --add-host gives the container the Ingress name's address (worker 1's), so the load
# does not need DNS for sslip.io: some DNS resolvers block private answers.
# --no-usage-report: k6 would otherwise send anonymous usage stats to Grafana Labs,
# so the pages are the only requests it makes.
Invoke-Docker run --rm --name skywatch-load `
    --add-host skywatch.192-168-60-11.sslip.io:192.168.60.11 `
    --volume "${loadJs}:/load.js:ro" `
    $image run --no-usage-report /load.js

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
#>

$ErrorActionPreference = 'Stop'

$image  = 'grafana/k6:2.3.0'
$script = Join-Path $PSScriptRoot 'load.js'

# A failing program does not stop PowerShell, even with 'Stop' above, so check its exit code.
function Invoke-Docker {
    # docker and k6 print progress on stderr. That is not a failure; the exit code is.
    # 'Continue' keeps PowerShell from stopping on that stderr text.
    $ErrorActionPreference = 'Continue'
    & docker @args
    if ($LASTEXITCODE -ne 0) { throw "'docker $args' failed with exit code $LASTEXITCODE." }
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'docker is not on PATH. Install Docker Desktop, then open a new PowerShell window.'
}

# The container's name keeps a second load from starting while one runs.
# --no-usage-report: k6 would otherwise send anonymous usage stats to Grafana Labs,
# so the pages are the only requests it makes.
Invoke-Docker run --rm --name skywatch-load `
    --volume "${script}:/load.js:ro" `
    $image run --no-usage-report /load.js

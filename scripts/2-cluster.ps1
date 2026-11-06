<#
.SYNOPSIS
    Bring-up step 2: the cluster, and the host kubeconfig.
.DESCRIPTION
    Builds the Ansible container from ansible/ and runs the playbook
    ansible/site.yml in it. The playbook installs K3s on the control plane over
    the Node network, joins the two workers to it, and writes .state/kubeconfig,
    which kubectl on this host uses. Safe to re-run: the playbook only changes
    what differs. Run 1-vms first. Does not need elevation.
#>

$ErrorActionPreference = 'Stop'

$repo       = Split-Path $PSScriptRoot
$ansibleDir = Join-Path $repo 'ansible'
$stateDir   = Join-Path $repo '.state'   # ignored by Git
$image      = 'skywatch-ansible'

# A failing program does not stop PowerShell, even with 'Stop' above, so check its exit code.
function Invoke-Docker {
    # docker and Ansible print progress and warnings on stderr. That is not a failure;
    # the exit code is. 'Continue' keeps PowerShell from stopping on that stderr text.
    $ErrorActionPreference = 'Continue'
    & docker @args
    if ($LASTEXITCODE -ne 0) { throw "'docker $args' failed with exit code $LASTEXITCODE." }
}

# 1. Prerequisites: Docker, and the SSH key 1-vms generates.
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'docker is not on PATH. Install Docker Desktop, then open a new PowerShell window.'
}
if (-not (Test-Path (Join-Path $stateDir 'id_ed25519'))) {
    throw "No SSH key at $stateDir\id_ed25519. Run 1-vms.ps1 first."
}

# 2. The Ansible container image. Docker's build cache makes a re-run quick.
Write-Host "Building the Ansible container image '$image'..."
Invoke-Docker build --quiet --tag $image $ansibleDir | Out-Null

# 3. The playbook. ansible/ is mounted read-only. .state/ is mounted read-write:
# the container reads the SSH key there and writes the kubeconfig there.
Invoke-Docker run --rm `
    --volume "${ansibleDir}:/ansible:ro" `
    --volume "${stateDir}:/state" `
    --workdir /ansible `
    $image ansible-playbook -i inventory.yml site.yml

Write-Host "K3s is up. Use the cluster from this host with: kubectl --kubeconfig .state\kubeconfig get nodes"

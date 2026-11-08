<#
.SYNOPSIS
    Bring-up step 1: creates the three cluster VMs (see docs/adr/0001).
.DESCRIPTION
    Launches the control plane and two workers with Multipass (Ubuntu 24.04).
    Each VM's default NIC is its Uplink, on Multipass's own network. A second
    NIC on the 'skywatch' switch gets a fixed Node network address through
    cloud-init. The SSH key pair Ansible logs in with is generated under .state/
    and injected the same way.
    Safe to re-run: an existing VM is started if needed and otherwise left
    unchanged. Run 0-network first. Does not need elevation.
#>

$ErrorActionPreference = 'Stop'

$switchName = 'skywatch'   # the Node network switch 0-network creates
$image      = '24.04'
# The VMs this script owns. down.ps1 removes exactly these names.
# The control plane has 4G because with 2G it ran out of memory applying the monitoring
# stack's CRDs. A re-run leaves an existing VM's size alone.
$nodes = @(
    [pscustomobject]@{ Name = 'skywatch-cp';      Address = '192.168.60.10'; Cpus = 2; Memory = '4G'; Disk = '15G' }
    [pscustomobject]@{ Name = 'skywatch-worker1'; Address = '192.168.60.11'; Cpus = 2; Memory = '4G'; Disk = '20G' }
    [pscustomobject]@{ Name = 'skywatch-worker2'; Address = '192.168.60.12'; Cpus = 2; Memory = '4G'; Disk = '20G' }
)
$stateDir = Join-Path (Split-Path $PSScriptRoot) '.state'   # ignored by Git
$keyPath  = Join-Path $stateDir 'id_ed25519'

# A failing program does not stop PowerShell, even with 'Stop' above, so check its exit code.
function Invoke-Multipass {
    & multipass @args
    if ($LASTEXITCODE -ne 0) { throw "'multipass $args' failed with exit code $LASTEXITCODE." }
}
function Get-Instances { @((Invoke-Multipass list --format json | ConvertFrom-Json).list) }

# 1. Prerequisites: Multipass, and the switch from 0-network.
if (-not (Get-Command multipass -ErrorAction SilentlyContinue)) {
    throw 'multipass is not on PATH. Install Multipass, then open a new PowerShell window.'
}
if ((Invoke-Multipass networks --format csv | ConvertFrom-Csv).Name -notcontains $switchName) {
    throw "Multipass does not see the switch '$switchName'. Run 0-network.ps1 (elevated) first."
}
$instances = Get-Instances

# 2. The SSH key pair, generated once.
if (-not (Test-Path $keyPath)) {
    if ($instances.name | Where-Object { $nodes.Name -contains $_ }) {
        throw "$keyPath is missing, but VMs exist that only accept the old key. Restore the key, or run down.ps1 and re-run."
    }
    New-Item -ItemType Directory -Force $stateDir | Out-Null
    # -N "" means no passphrase. The arguments go as one string because
    # Windows PowerShell 5.1 drops an empty "" argument when it calls a program.
    $keygen = Start-Process ssh-keygen -NoNewWindow -Wait -PassThru `
        -ArgumentList ('-q -t ed25519 -N "" -C skywatch-bring-up -f "{0}"' -f $keyPath)
    if ($keygen.ExitCode -ne 0) { throw "ssh-keygen failed with exit code $($keygen.ExitCode)." }
    Write-Host "Generated the SSH key pair $keyPath."
} else {
    Write-Host "SSH key pair $keyPath already exists."
}
$publicKey = (Get-Content "$keyPath.pub" -Raw).Trim()

# 3. The VMs.
foreach ($node in $nodes) {
    $vm = $instances | Where-Object name -eq $node.Name

    if (-not $vm) {
        # The Node network NIC gets a fixed MAC, 52:54:00:60:00:<last octet of its address>,
        # so cloud-init can find it by MAC. mode=manual: Multipass leaves that NIC to us.
        $mac = '52:54:00:60:00:' + $node.Address.Split('.')[-1]
        $cloudInit = Join-Path $stateDir "cloud-init-$($node.Name).yaml"
        # In the here-string, `$ passes a $ through to the VM's shell.
        Set-Content -Path $cloudInit -Encoding Ascii -Value @"
#cloud-config
# Rendered by scripts/1-vms.ps1 for $($node.Name). cloud-init applies it once, at first boot.
ssh_authorized_keys:
  - $publicKey
write_files:
  # The Node network NIC. Hyper-V offers the two NICs in random order, so its kernel
  # name varies (eth0, eth1 or cloud-init's cirename0); set-name gives it a fixed one,
  # outside the ethN names, for K3s's flannel-iface. No gateway, so the default route
  # stays on the Uplink (eth0).
  - path: /etc/netplan/60-skywatch.yaml
    permissions: '0600'   # netplan warns when its files are readable by others
    content: |
      network:
        version: 2
        ethernets:
          skywatch0:
            match:
              macaddress: "$mac"
            set-name: skywatch0
            dhcp4: false
            addresses: [$($node.Address)/24]
runcmd:
  # Sets up only the Node network NIC now, found by its MAC. Later boots use the file above.
  # The NIC goes down first, so ip can rename it.
  # This doesn't use netplan apply. netplan apply also reconfigures the Uplink, which drops
  # its DHCP lease and gets a new address. The host then has two neighbor entries for the
  # Uplink's MAC, and Multipass can pick the stale one until the launch times out.
  - |
    set -e
    nic=`$(ip -br link | awk '`$3 == "$mac" {print `$1}')
    [ -n "`$nic" ] || { echo "no NIC with MAC $mac" >&2; exit 1; }
    ip link set dev "`$nic" down
    ip link set dev "`$nic" name skywatch0
    ip link set dev skywatch0 up
    ip address add $($node.Address)/24 dev skywatch0
"@
        Invoke-Multipass launch $image --name $node.Name --cpus $node.Cpus --memory $node.Memory --disk $node.Disk `
            --network "name=$switchName,mode=manual,mac=$mac" --cloud-init $cloudInit
        Write-Host "$($node.Name) at $($node.Address): created."
        continue
    }

    if ($vm.state -eq 'Running') {
        $done = 'already running; left unchanged'
    } else {
        Invoke-Multipass start $node.Name   # e.g. after a host reboot
        $done = "started (it was $($vm.state))"
        $vm = Get-Instances | Where-Object name -eq $node.Name
    }
    if ($vm.ipv4 -notcontains $node.Address) {
        throw "$($node.Name) exists but is not on the Node network at $($node.Address), so it is not a VM this script created, or its network is broken. Remove it with 'multipass delete --purge $($node.Name)', then re-run."
    }
    Write-Host "$($node.Name) at $($node.Address): $done."
}

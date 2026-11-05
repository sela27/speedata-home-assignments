<#
.SYNOPSIS
    Tears Bring-up down, so it can be rehearsed from scratch.
.DESCRIPTION
    Deletes and purges the three VMs 1-vms creates, and no other instance.
    The Node network switch stays unless -RemoveSwitch is given. Safe to re-run.
.PARAMETER RemoveSwitch
    Also removes the 'skywatch' switch, and with it the host's 192.168.60.1.
    Needs an elevated PowerShell, and only removes the switch 0-network created
    (marked in its Notes).
#>
param([switch] $RemoveSwitch)

$ErrorActionPreference = 'Stop'

$vmNames    = 'skywatch-cp', 'skywatch-worker1', 'skywatch-worker2'   # the VMs 1-vms creates
$switchName = 'skywatch'
$marker     = 'skywatch-node-network'   # 0-network writes this to the switch's Notes

# Check elevation before anything else, so a refused run changes nothing.
if ($RemoveSwitch) {
    $principal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw '-RemoveSwitch needs an elevated PowerShell (Run as Administrator). Nothing was changed.'
    }
}

# A failing program does not stop PowerShell, even with 'Stop' above, so check its exit code.
function Invoke-Multipass {
    & multipass @args
    if ($LASTEXITCODE -ne 0) { throw "'multipass $args' failed with exit code $LASTEXITCODE." }
}

# 1. The VMs.
$instances = @((Invoke-Multipass list --format json | ConvertFrom-Json).list)
foreach ($name in $vmNames) {
    if ($instances.name -contains $name) {
        Invoke-Multipass delete --purge $name
        Write-Host "Deleted $name."
    } else {
        Write-Host "$name does not exist; nothing to delete."
    }
}

# 2. The switch, only when asked.
if (-not $RemoveSwitch) {
    Write-Host "Left the Node network switch '$switchName' in place. To remove it too, run down.ps1 -RemoveSwitch elevated."
    return
}
$switches = @(Get-VMSwitch -Name $switchName -ErrorAction SilentlyContinue)
if ($switches.Count -eq 0) {
    Write-Host "No switch named '$switchName'; nothing to remove."
} elseif ($switches.Count -gt 1 -or $switches[0].Notes -ne $marker) {
    throw "Switch '$switchName' was not created by 0-network (or there are several), so it is left alone. Remove it by hand if you mean to."
} else {
    $switches[0] | Remove-VMSwitch -Force
    Write-Host "Removed the Node network switch '$switchName' and the host's address on it."
}

#Requires -RunAsAdministrator
#Requires -Modules Hyper-V
<#
.SYNOPSIS
    Bring-up step 0 (elevated): creates the Node network (see docs/adr/0001).
.DESCRIPTION
    Ensures the Node network switch 'skywatch' exists and that the host has
    192.168.60.1/24 on it. Safe to re-run. It only uses a switch it created
    itself (marked in the switch's Notes) and never touches any other switch.
#>

$ErrorActionPreference = 'Stop'

$switchName   = 'skywatch'
$marker       = 'skywatch-node-network'   # written to the switch's Notes when this script creates it
$hostAddress  = '192.168.60.1'
$prefixLength = 24
$hostAdapter  = "vEthernet ($switchName)"   # the host NIC Hyper-V creates for an Internal switch

# 1. The switch: create and mark it if missing; otherwise use it only if it carries the marker.
$switches = @(Get-VMSwitch -Name $switchName -ErrorAction SilentlyContinue)
if ($switches.Count -gt 1) {
    throw "Found $($switches.Count) switches named '$switchName', so the Node network switch is ambiguous. Rename or remove the extras, then re-run."
}
$switch = $switches[0]
if (-not $switch) {
    New-VMSwitch -Name $switchName -SwitchType Internal -Notes $marker | Out-Null
    Write-Host "Created the Node network switch '$switchName'."
} elseif ($switch.Notes -ne $marker) {
    throw "Switch '$switchName' exists but this script did not create it (its Notes lack '$marker'). Existing switches are never reused. Remove or rename it, then re-run."
} elseif ($switch.SwitchType -ne 'Internal') {
    throw "Switch '$switchName' is $($switch.SwitchType), not Internal. Remove it, then re-run."
} else {
    Write-Host "Node network switch '$switchName' already exists; leaving it unchanged."
}

# 2. The host's Node network address on that switch.
$address = Get-NetIPAddress -InterfaceAlias $hostAdapter -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -eq $hostAddress }
if (-not $address) {
    New-NetIPAddress -InterfaceAlias $hostAdapter -IPAddress $hostAddress -PrefixLength $prefixLength | Out-Null
    Write-Host "Assigned $hostAddress/$prefixLength to '$hostAdapter'."
} elseif ($address.PrefixLength -ne $prefixLength) {
    throw "'$hostAdapter' has $hostAddress/$($address.PrefixLength), not /$prefixLength. Remove that address, then re-run."
} else {
    Write-Host "'$hostAdapter' already has $hostAddress/$prefixLength."
}

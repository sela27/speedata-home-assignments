#Requires -RunAsAdministrator
#Requires -Modules Hyper-V
<#
.SYNOPSIS
    Bring-up step 0 (elevated): creates the Node network (see docs/adr/0001).
.DESCRIPTION
    Ensures the internal Hyper-V switch 'skywatch' exists and that the host has
    192.168.60.1/24 on it. Safe to re-run. It never touches any other switch.
#>

$ErrorActionPreference = 'Stop'

$switchName  = 'skywatch'
$hostAddress = '192.168.60.1'
$prefix      = 24
$hostAdapter = "vEthernet ($switchName)"   # the host NIC Hyper-V creates for an internal switch

# 1. The switch: create it only if it is missing.
$switch = Get-VMSwitch -Name $switchName -ErrorAction SilentlyContinue
if (-not $switch) {
    New-VMSwitch -Name $switchName -SwitchType Internal | Out-Null
    Write-Host "Created internal switch '$switchName'."
} elseif ($switch.SwitchType -ne 'Internal') {
    throw "Switch '$switchName' exists but is $($switch.SwitchType), not Internal. Remove or rename it, then re-run."
} else {
    Write-Host "Switch '$switchName' already exists; leaving it unchanged."
}

# 2. The host's Node network address on that switch.
$address = Get-NetIPAddress -InterfaceAlias $hostAdapter -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -eq $hostAddress -and $_.PrefixLength -eq $prefix }
if (-not $address) {
    New-NetIPAddress -InterfaceAlias $hostAdapter -IPAddress $hostAddress -PrefixLength $prefix | Out-Null
    Write-Host "Assigned $hostAddress/$prefix to '$hostAdapter'."
} else {
    Write-Host "'$hostAdapter' already has $hostAddress/$prefix."
}

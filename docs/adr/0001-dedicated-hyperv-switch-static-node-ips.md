# Dedicated Hyper-V switch with static node IPs

Multipass's default network addresses VMs over DHCP, and those addresses drift, which would break the K3s agent-to-server URL, the host kubeconfig and the Ingress address. Bring-up therefore creates its own Hyper-V switch (`skywatch`, `192.168.60.0/24`, host at `.1`) as the Node network: each VM gets a NIC on it with a static IP set through cloud-init (control plane `.10`, workers `.11` and `.12`), K3s binds to it (node IP and flannel interface), and the default network stays only as the Uplink. The cost is one elevated PowerShell step during Bring-up.

## Considered Options

- **Default Switch with `*.mshome.net` names**: names survive a reboot, but flannel, certificates and the Ingress address are still IP-bound, so recovery isn't guaranteed.
- **Re-run the playbook after every reboot**: simplest, but fragile in a live demo.
- **Reuse the existing `Mgmt` switch on the dev laptop**: rejected because Bring-up must create everything it depends on, so it can be reproduced on a clean machine.

## Consequences

- **Independent of the Multipass driver**: under `hcs` (Multipass 1.17) the default network is a per-zone network, and in the [#4](https://github.com/sela27/speedata-home-assignments/issues/4) spike one VM restart changed its address; under the older `hyperv` driver it was the Default Switch, whose subnet is re-randomised on every Windows reboot.
- **How the static IP is applied**: the Node network NIC must be found by a fixed MAC ([#18](https://github.com/sela27/speedata-home-assignments/issues/18)) and set up without `netplan apply` ([#52](https://github.com/sela27/speedata-home-assignments/issues/52)), as the README's [problems with the Node network and the VMs](../../README.md#the-node-network-and-the-vms) explain.

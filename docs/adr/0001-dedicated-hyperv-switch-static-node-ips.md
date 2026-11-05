# Dedicated Hyper-V switch with static node IPs

Multipass puts each VM's default NIC on a network it manages and addresses it over DHCP. With the `hcs` driver (Multipass 1.17) this is a per-zone NAT network, and in the #4 spike a single VM restart changed its address. With the older `hyperv` driver it was the Default Switch, whose subnet is re-randomised on every Windows reboot. Either way, node IPs would drift and break the K3s agent-to-server URL, the host kubeconfig and the Ingress address. Bring-up therefore creates its own internal Hyper-V switch (`skywatch`, `192.168.60.0/24`, host at `.1`) as the Node network. Each VM gets a second NIC on it with a static IP set through cloud-init (control plane `.10`, workers `.11` and `.12`), and K3s binds to it (node IP and flannel interface). The default NIC stays only as the Uplink. The cost is one elevated PowerShell step during Bring-up.

## Considered Options

- **Default Switch with `*.mshome.net` names**: names survive a reboot, but flannel, certificates and the Ingress address are still IP-bound, so recovery isn't guaranteed.
- **Re-run the playbook after every reboot**: simplest, but fragile in a live demo.
- **Reuse the existing `Mgmt` switch on the dev laptop**: rejected because Bring-up must create everything it depends on, so it can be reproduced on a clean machine.

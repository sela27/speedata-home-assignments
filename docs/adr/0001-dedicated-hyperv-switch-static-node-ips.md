# Dedicated Hyper-V switch with static node IPs

Multipass on Hyper-V attaches VMs to the Default Switch, whose subnet is re-randomised on every Windows reboot, so node IPs would drift and break the K3s agent-to-server URL, the host kubeconfig and the Ingress address. Bring-up therefore creates its own internal Hyper-V switch (`skywatch`, `192.168.60.0/24`, host at `.1`) as the Node network: each VM gets a NIC on it with a static IP set through cloud-init (control plane `.10`, workers `.11` and `.12`), K3s binds to it (node IP and flannel interface), and the Default Switch NIC stays only as the Uplink. The cost is one elevated PowerShell step during Bring-up.

## Considered Options

- **Default Switch with `*.mshome.net` names**: names survive a reboot, but flannel, certificates and the Ingress address are still IP-bound, so recovery isn't guaranteed.
- **Re-run the playbook after every reboot**: simplest, but fragile in a live demo.
- **Reuse the existing `Mgmt` switch on the dev laptop**: rejected because Bring-up must create everything it depends on, so it can be reproduced on a clean machine.

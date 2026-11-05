# Dedicated Hyper-V switch with static node IPs

Multipass on Hyper-V attaches VMs to the Default Switch, whose subnet is re-randomised on every Windows reboot. The node IPs would drift, breaking the K3s agent-to-server URL, the host kubeconfig and the Ingress address. So the setup creates its own internal Hyper-V switch (`skywatch`, `192.168.60.0/24`, host at `.1`) and gives each VM a second NIC on it with a static IP set through cloud-init (control plane `.10`, workers `.11` and `.12`). K3s binds to that NIC (`--node-ip`, `--flannel-iface`); the Default Switch NIC stays only for internet access. The cost is one elevated PowerShell step during setup.

## Considered Options

- **Default Switch with `*.mshome.net` names**: names survive a reboot, but flannel, certificates and the Ingress address are still IP-bound, so recovery isn't guaranteed.
- **Re-run the playbook after every reboot**: simplest, but fragile in a live demo.
- **Reuse the existing `Mgmt` switch on the dev laptop**: rejected because the setup must create everything it depends on, so it can be reproduced on a clean machine.

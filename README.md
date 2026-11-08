# SkyWatch

A small weather-query app (a Flask frontend and a backend API that calls Open-Meteo) running on a local multi-node K3s cluster, delivered through CI (GitHub Actions → GHCR) and GitOps (ArgoCD).

> **Status: work in progress.** Bring-up and verification are below. The architecture, the decisions, the problems and the proof of the Key flow are written later in milestone M6.

## Chosen path

**Path A**: three Ubuntu 24.04 VMs created with Multipass (one control plane, two workers), with K3s installed by Ansible.

## Supported host

Windows 11 Pro with Hyper-V. Other host operating systems are not supported.

The VMs take 6 vCPU, 12 GiB RAM and up to 55 GiB of disk from the host:

| VM | Node network address | vCPU | RAM | Disk |
| --- | --- | --- | --- | --- |
| `skywatch-cp` (control plane) | 192.168.60.10 | 2 | 4 GiB | 15 GiB |
| `skywatch-worker1` | 192.168.60.11 | 2 | 4 GiB | 20 GiB |
| `skywatch-worker2` | 192.168.60.12 | 2 | 4 GiB | 20 GiB |

The disks grow as they fill: after two days of running, the three VMs had 15 GiB in use together. Docker Desktop's own VM comes on top of this. Tested on a host with 20 logical processors and 32 GiB RAM.

Bring-up writes everything it generates (the SSH key pair, the host kubeconfig, rendered cloud-init files) under `.state/`, which Git ignores.

## Prerequisites

Tested with these versions. Each check runs in a normal Windows PowerShell window.

| Tool | Tested with | Check | What it is for |
| --- | --- | --- | --- |
| Windows 11 Pro, with Hyper-V on | 25H2 (build 26200) | `Get-Service vmms` is `Running`, and `Get-Module -ListAvailable Hyper-V` lists the module | the VMs, and the switch for the Node network |
| Windows PowerShell | 5.1.26100 | `$PSVersionTable.PSVersion` | runs the scripts. They were tested in 5.1 only, not in PowerShell 7. |
| [Multipass](https://canonical.com/multipass/install) | 1.17.0, `hcs` driver | `multipass version`, and `multipass get local.driver` prints `hcs` | creates the three VMs |
| [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/) | 4.80.0 (Engine 29.6.1), WSL 2 backend | `docker version` prints a `Server` section | runs the Ansible container (`2-cluster`) and k6 (`load`) |
| [kubectl](https://kubernetes.io/docs/tasks/tools/install-kubectl-windows/) | v1.36.0 | `kubectl version --client` | the passwords and the checks. Use 1.36 to 1.38, within one minor version of K3s v1.37. |
| [Git](https://git-scm.com/downloads/win) | 2.53.0 | `git --version` | the clone |
| OpenSSH client | 9.5p2, built into Windows 11 | `Get-Command ssh-keygen` finds it, and `ssh -V` prints the version | `1-vms` generates the SSH key that Ansible logs in with |
| [Helm](https://helm.sh/docs/intro/install/) (optional) | v4.1.4 | `helm version` | not used by any Bring-up step: `2-cluster` uses the Helm v4.3.1 inside the Ansible container. Only for running CI's chart checks locally, such as `helm lint --strict charts/skywatch`. |

`curl.exe`, used in the checks below, ships with Windows 11.

### On a fresh Windows 11 Pro machine

Do these once, before the first script:

1. **Hardware virtualization on** in the BIOS/UEFI settings. Hyper-V and Docker Desktop both need it.
2. **Hyper-V on.** In an elevated PowerShell (Start, type `Windows PowerShell`, right-click, **Run as administrator**), run Microsoft's command, then answer `Y` to restart ([Install Hyper-V](https://learn.microsoft.com/en-us/windows-server/virtualization/hyper-v/get-started/install-hyper-v)):

   ```powershell
   Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -All
   ```

   `0-network` also needs Hyper-V's PowerShell module, which comes with Hyper-V's management tools: without it, the script's `#Requires -Modules Hyper-V` line stops it. After the restart, if `Get-Module -ListAvailable Hyper-V` lists nothing, add the module in an elevated window, then check again in a new window:

   ```powershell
   Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-Management-PowerShell -All
   ```

   Or, in **Turn Windows features on or off**, under **Hyper-V** and **Hyper-V Management Tools**, select **Hyper-V Module for Windows PowerShell**.
3. **Install the tools** in the table. The Multipass installer asks for administrator rights. Then open a new PowerShell window, so that `PATH` has them.
4. **Docker Desktop running.** It doesn't start by itself after the install: start it from the Start menu and accept its terms. `docker version` must print a `Server` section.
5. **Scripts allowed.** On Windows clients, the default execution policy is `Restricted`, which runs no scripts at all ([about_Execution_Policies](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies?view=powershell-5.1)). Allow local scripts for your user, once. This needs no elevation:

   ```powershell
   Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
   ```

   To change nothing that lasts, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned` in each new window instead. A `CurrentUser` policy belongs to that user only: if your elevated window runs as another account, run the `-Scope Process` line there too. `RemoteSigned` runs the scripts of a `git clone`. It blocks the scripts of a ZIP downloaded in a browser, which marks them as from the internet: unblock those with `Get-ChildItem -Recurse | Unblock-File`.
6. **One elevated window.** `0-network` needs **Run as administrator**, because it creates a Hyper-V switch. Everything else runs in a normal window.

## Bring-up

Run each step from the repository root in Windows PowerShell. Every script is safe to re-run: if one fails, fix what its error names, then run the same step again.

### Clone the repository

```powershell
git clone https://github.com/sela27/speedata-home-assignments.git
cd speedata-home-assignments
```

ArgoCD deploys what is on `main` on GitHub, not what is in your clone. A local edit changes nothing in the cluster until it reaches `main` (the Key flow).

- **Expected:** a `speedata-home-assignments` folder. The commands below run in it.
- **Takes:** seconds.
- **Re-run:** not needed. `git pull` updates the clone.

### 0. The Node network: `0-network` (elevated)

Open a PowerShell window with **Run as administrator**. It starts in `C:\Windows\System32`, so `cd` to your clone first: `Get-Location` in your normal window shows its path. For a clone made where a new normal window starts, your home folder:

```powershell
cd "$HOME\speedata-home-assignments"
.\scripts\0-network.ps1
```

It creates the internal Hyper-V switch `skywatch` and gives the host 192.168.60.1/24 on it: the Node network ([ADR-0001](docs/adr/0001-dedicated-hyperv-switch-static-node-ips.md)). It marks the switch as its own in the switch's Notes, and touches no other switch.

- **Expected:**

  ```text
  Created the Node network switch 'skywatch'.
  Assigned 192.168.60.1/24 to 'vEthernet (skywatch)'.
  ```

  In a window that is not elevated, the script stops at once and changes nothing: `The script '0-network.ps1' cannot be run because it contains a "#requires" statement for running as Administrator.`
- **Takes:** seconds.
- **Re-run:** safe. It prints `Node network switch 'skywatch' already exists; leaving it unchanged.` and `'vEthernet (skywatch)' already has 192.168.60.1/24.` If a switch named `skywatch` exists that it didn't create, it stops and changes nothing.

You can close the elevated window now.

### 1. The VMs: `1-vms`

In a normal PowerShell window:

```powershell
.\scripts\1-vms.ps1
```

It generates the SSH key pair `.state\id_ed25519`, then launches the three VMs with Multipass, one after the other. Each VM has two NICs. Its default NIC, on Multipass's own network, is its Uplink to the internet. The second NIC, on the `skywatch` switch, gets the VM's fixed Node network address through cloud-init. cloud-init also installs the public key, so Ansible can log in.

- **Expected:** `Generated the SSH key pair ...\.state\id_ed25519.`, Multipass's progress for each VM (`Launched: skywatch-cp in zone1`), and one line per VM:

  ```text
  skywatch-cp at 192.168.60.10: created.
  skywatch-worker1 at 192.168.60.11: created.
  skywatch-worker2 at 192.168.60.12: created.
  ```

  `multipass list` then shows the three VMs `Running`, each with its 192.168.60.x address.
- **Takes:** about 3 minutes, about a minute per VM, once Multipass has the Ubuntu 24.04 image. The first launch on a machine downloads the image first.
- **Re-run:** safe. A running VM is left unchanged (`skywatch-cp at 192.168.60.10: already running; left unchanged.`). A stopped VM, for example after a host reboot, is started. A re-run never resizes a VM. The script stops if `.state\id_ed25519` is missing while the VMs exist, because they accept only that key: restore the key, or run `down` first.

### 2. The cluster and ArgoCD: `2-cluster`

```powershell
.\scripts\2-cluster.ps1
```

It builds the Ansible container image from `ansible/` and runs the playbook `ansible/site.yml` in it, over the Node network:

1. K3s v1.37.2+k3s1 on the control plane, which is tainted `NoSchedule`, so app pods run only on the workers.
2. The two workers join, with a token read from the control plane at run time and never stored.
3. `.state\kubeconfig` for kubectl on this host.
4. ArgoCD (chart 10.14.0, ArgoCD v3.6.1), the Grafana admin Secret with a random password, and the root Application.

From then on ArgoCD deploys everything else from `apps/` on `main`: the `skywatch` app and the `monitoring` app (Prometheus and Grafana).

- **Expected:** `Building the Ansible container image 'skywatch-ansible'...`, then each Ansible task, then a `PLAY RECAP` with `unreachable=0 failed=0` for `localhost`, `skywatch-cp`, `skywatch-worker1` and `skywatch-worker2`. On the ArgoCD task, a `[DEPRECATION WARNING]` and a `[WARNING]` about it are normal: the Helm module flags its own deprecated return value. A re-run adds a second `[WARNING]`, because the helm diff plugin isn't installed. It ends with the URLs and the password commands (see [URLs and passwords](#urls-and-passwords)):

  ```text
  K3s and ArgoCD are up. ArgoCD deploys the apps in apps/ from Git, on main. From this host:
    the cluster:  kubectl --kubeconfig .state\kubeconfig get nodes
    SkyWatch:     http://skywatch.192-168-60-11.sslip.io  (once ArgoCD has synced it)
    ...
  ```

- **Takes:** about 2.5 minutes. The first run on a machine also builds the Ansible image. After that, ArgoCD needs about 1.5 more minutes until its three apps are `Synced` and `Healthy`. On the way they show `OutOfSync`, `Progressing` or `Degraded` while images pull: that is normal.
- **Re-run:** safe, and takes seconds. On a healthy cluster it reports `changed=0` on all four hosts (see the [checklist](#verification-checklist)). It installs K3s only where it is missing or at another version, and restarts K3s only when its config changed. It never rotates the Grafana password. It puts the root Application back if it was edited by hand. A first run that stopped halfway, for example on an image-pull timeout, completes when run again.

### Load for the dashboard and the HPA: `load` (optional)

```powershell
.\scripts\load.ps1
```

It runs the k6 load generator ([scripts/load.js](scripts/load.js)) in a pinned `grafana/k6:2.3.0` container. For 5 minutes k6 asks the frontend's Ingress for pages, 10 cities in turn, at up to 45 pages a second. It calls nothing else: Open-Meteo sees only the backend's cache misses, far under its free limit of 10,000 calls a day.

- **Expected:** k6's progress, then its summary. The backend HPA scales from 2 replicas to 3 about 2 minutes in, and back to 2 about 5 minutes after the load ends: `kubectl --kubeconfig .state\kubeconfig -n skywatch get hpa` shows the `REPLICAS`. A few pages may fail while the backend's caches are cold, when their Open-Meteo call passes the backend's 5 s timeout. Ctrl+C stops k6 early: it prints its summary, exits with code 105, and the script reports that exit code as a failure.
- **Takes:** 5 minutes.
- **Re-run:** safe once the previous run has ended. While one runs, a second can't start: its container name is taken.

### Tear-down: `down`

```powershell
.\scripts\down.ps1
```

It deletes and purges the three VMs, and no other Multipass instance. The switch stays, and so does `.state\`: the next `1-vms` reuses the SSH key, and the next `2-cluster` rewrites the kubeconfig.

- **Expected:**

  ```text
  Deleted skywatch-cp.
  Deleted skywatch-worker1.
  Deleted skywatch-worker2.
  Left the Node network switch 'skywatch' in place. To remove it too, run down.ps1 -RemoveSwitch elevated.
  ```

  `multipass list` then prints `No instances found.`, unless you have other instances.
- **Takes:** seconds.
- **Re-run:** safe. It prints `skywatch-cp does not exist; nothing to delete.` for each VM.

To remove the switch and the host's 192.168.60.1 too, run it in an elevated window, in your clone (`cd` there first, as for `0-network`):

```powershell
.\scripts\down.ps1 -RemoveSwitch
```

It removes only a switch that `0-network` created, and prints:

```text
Deleted skywatch-cp.
Deleted skywatch-worker1.
Deleted skywatch-worker2.
Removed the Node network switch 'skywatch' and the host's address on it.
```

In a window that is not elevated, it stops before deleting anything: `-RemoveSwitch needs an elevated PowerShell (Run as Administrator). Nothing was changed.`

### If a step fails

- `1-vms` can stop with `launch failed: ... timed out waiting for initialization to complete`. When that happened, Multipass had given up, not the VM: cloud-init's `netplan apply` renewed the VM's Uplink address during the launch, and Multipass kept waiting for SSH at the old one. A re-run then stops at that VM with `exists but is not on the Node network`. Remove only that VM, then run `1-vms` again. It leaves the other VMs unchanged and creates this one in about a minute:

  ```powershell
  multipass delete --purge skywatch-worker2   # the VM named in the error
  .\scripts\1-vms.ps1
  ```

- After the host moves to another network, ArgoCD can show `lookup github.com ... server misbehaving`: CoreDNS still forwards to the old network's DNS servers. Restart it with `kubectl --kubeconfig .state\kubeconfig -n kube-system rollout restart deployment/coredns`.
- After a host reboot, `multipass list` may show a VM `Stopped`. Run `.\scripts\1-vms.ps1`: it starts it. The addresses are fixed, so the kubeconfig and the URLs keep working.

## Using the cluster

### The kubeconfig

`2-cluster` writes `.state\kubeconfig`. It points at the API server on the control plane's Node network address, `https://192.168.60.10:6443`, and holds the cluster's admin credentials. Git ignores it. Run kubectl from the repository root:

```powershell
kubectl --kubeconfig .state\kubeconfig get nodes
```

Or set it once per window, after which plain `kubectl` works. [docs/alerts.md](docs/alerts.md) assumes this:

```powershell
$env:KUBECONFIG = "$PWD\.state\kubeconfig"
kubectl get nodes
```

### URLs and passwords

| What | URL | Login |
| --- | --- | --- |
| SkyWatch | <http://skywatch.192-168-60-11.sslip.io> | none |
| ArgoCD | <http://argocd.192-168-60-11.sslip.io> | `admin`, and the password below |
| Grafana | <http://grafana.192-168-60-11.sslip.io> | `admin`, and the password below. The SkyWatch dashboard is at `/d/skywatch/skywatch`. |
| Prometheus | no Ingress | `kubectl port-forward`, see [docs/alerts.md](docs/alerts.md) |

sslip.io answers each of these names with the address inside it, 192.168.60.11 (worker 1). Traefik, K3s's Ingress controller, routes each name to its app. Plain HTTP: there is no TLS.

The passwords, from the repository root, exactly as `2-cluster` prints them. ArgoCD generated its own when it was installed. `2-cluster` generated Grafana's, and later runs never change it.

```powershell
kubectl --kubeconfig .state\kubeconfig -n argocd get secret argocd-initial-admin-secret -o go-template='{{.data.password | base64decode}}'
kubectl --kubeconfig .state\kubeconfig -n monitoring get secret grafana-admin -o go-template='{{index .data `admin-password` | base64decode}}'
```

Both work in Windows PowerShell 5.1. Keep the backquotes around `admin-password`: 5.1 drops the double quotes inside a program's argument, so `"admin-password"` would break the template.

### If your DNS resolver blocks sslip.io

Some DNS resolvers drop answers that point at a private address (a protection against DNS rebinding), and then these names don't resolve. Check:

```powershell
Resolve-DnsName skywatch.192-168-60-11.sslip.io
```

It should answer `192.168.60.11`. If it fails, add these lines to the hosts file, `C:\Windows\System32\drivers\etc\hosts`. Editing that file needs an elevated editor: in a window opened with **Run as administrator**, run `notepad C:\Windows\System32\drivers\etc\hosts`.

```text
192.168.60.11 skywatch.192-168-60-11.sslip.io
192.168.60.11 argocd.192-168-60-11.sslip.io
192.168.60.11 grafana.192-168-60-11.sslip.io
```

The lines replace only the DNS answer. Traefik still sees the same names. This was checked without touching the hosts file, with curl's `--resolve` option, which pins a name to an address the same way:

```powershell
curl.exe -s -o NUL -w "%{http_code}\n" --resolve skywatch.192-168-60-11.sslip.io:80:192.168.60.11 http://skywatch.192-168-60-11.sslip.io/
```

That prints `200` for SkyWatch and ArgoCD, and `302` (a redirect to the login page) for Grafana. `load` doesn't need the fallback: it gives the k6 container the address itself. Remove the lines when you no longer need them.

## Verification checklist

Run these from the repository root after Bring-up. Each item gives a command and what to look for.

1. **The nodes are Ready.**

   ```powershell
   kubectl --kubeconfig .state\kubeconfig get nodes
   ```

   Three nodes, all `Ready`, all `v1.37.2+k3s1`. `skywatch-cp` has the role `control-plane`. Its taint keeps app pods off it:

   ```powershell
   kubectl --kubeconfig .state\kubeconfig describe node skywatch-cp | Select-String Taints
   ```

   prints `node-role.kubernetes.io/control-plane:NoSchedule`.
2. **The app pods run only on the workers.**

   ```powershell
   kubectl --kubeconfig .state\kubeconfig -n skywatch get pods -o wide
   ```

   Two `skywatch-backend` pods and one `skywatch-frontend` pod, all `Running` and `1/1`. The `NODE` column shows only `skywatch-worker1` and `skywatch-worker2`, never `skywatch-cp`.
3. **The HPA holds at least 2 backend replicas.**

   ```powershell
   kubectl --kubeconfig .state\kubeconfig -n skywatch get hpa
   ```

   `MINPODS 2`, `MAXPODS 5`, `REPLICAS` 2 or more, and `TARGETS` with a number, such as `cpu: 2%/70%`, not `<unknown>`.
4. **ArgoCD is Synced and Healthy.**

   ```powershell
   kubectl --kubeconfig .state\kubeconfig -n argocd get applications
   ```

   `monitoring`, `root` and `skywatch`, each `Synced` and `Healthy`. Right after `2-cluster`, give them about 2 minutes. In the ArgoCD UI, each app shows the commit it synced, the latest on `main`.
5. **The URLs work.**

   ```powershell
   curl.exe -s "http://skywatch.192-168-60-11.sslip.io/?city=Haifa" | Select-String "<h2>|Frontend"
   curl.exe -s http://argocd.192-168-60-11.sslip.io/api/version
   curl.exe -s http://grafana.192-168-60-11.sslip.io/api/health
   ```

   SkyWatch prints `<h2>Haifa, Israel</h2>` and its footer, the line with `Frontend <sha>` and `Backend <sha>`: the commit each running image was built from. ArgoCD answers `{"Version":"v3.6.1"}`, and Grafana `"database": "ok"`. Then open the three URLs in a browser, and log in to ArgoCD and Grafana as `admin` with the [passwords](#urls-and-passwords).
6. **The dashboard has data under load.** Run [`.\scripts\load.ps1`](#load-for-the-dashboard-and-the-hpa-load-optional). While it runs, open <http://grafana.192-168-60-11.sslip.io/d/skywatch/skywatch>. Every panel shows data: about 45 requests a second per service, an error rate near 0, the latency percentiles, Open-Meteo's p95, a cache hit ratio near 1, the backend's CPU against its request, and the replicas going from 2 to 3.
7. **A second `2-cluster` run changes nothing.**

   ```powershell
   .\scripts\2-cluster.ps1
   ```

   The `PLAY RECAP` shows `changed=0` and `failed=0` for `localhost`, `skywatch-cp`, `skywatch-worker1` and `skywatch-worker2`. A recorded run is in [docs/evidence/2-cluster-second-run.txt](docs/evidence/2-cluster-second-run.txt).

## Where to look

- The spec: [issue #1](https://github.com/sela27/speedata-home-assignments/issues/1). Its sub-issues are the tickets, with their order of work.
- Key decisions: [docs/adr/](docs/adr/)
- The alerts, and how to trigger each one: [docs/alerts.md](docs/alerts.md)
- Load for the dashboard and the HPA: `scripts\load.ps1` runs k6 on [scripts/load.js](scripts/load.js)
- Project vocabulary: [GLOSSARY.md](GLOSSARY.md)
- The assignment itself: [skywatch-assignment.md](skywatch-assignment.md)

#!/bin/sh
# Entrypoint of the Ansible container: prepares the SSH key, then runs the command.
#
# Bring-up mounts .state/ at /state. A file bind-mounted from Windows shows up
# world-readable (mode 777) inside Linux, and ssh refuses a private key that
# others can read. So copy the key to a private file (mode 600) and point
# Ansible at the copy.
set -eu

if [ -f /state/id_ed25519 ]; then
    install -D -m 600 /state/id_ed25519 "$HOME/.ssh/id_ed25519"
    export ANSIBLE_PRIVATE_KEY_FILE="$HOME/.ssh/id_ed25519"
else
    # Not fatal: commands that need no node, like ansible --version, still run.
    echo "warning: no SSH key at /state/id_ed25519; mount .state/ at /state to reach the nodes" >&2
fi

exec "$@"

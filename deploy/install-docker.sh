#!/bin/bash
# Docker Engine + Compose plugin on Ubuntu, following
# https://docs.docker.com/engine/install/ubuntu/ (apt repository method).
#
# Usage: sudo deploy/install-docker.sh [user]
# The optional user is added to the group "docker" (docker without sudo; this is
# equivalent to root access). Log out and in again afterwards.
set -euo pipefail
if [ "$(id -u)" -ne 0 ]; then
    echo "Run with sudo." >&2
    exit 1
fi
export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

tee /etc/apt/sources.list.d/docker.sources >/dev/null <<SRC
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
SRC

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

systemctl enable --now docker
# Post-install step of the official guide: use docker without sudo.
if [ -n "${1:-}" ]; then
    usermod -aG docker "$1"
fi
docker --version
docker compose version

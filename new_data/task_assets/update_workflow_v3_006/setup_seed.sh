#!/usr/bin/env bash
set -euo pipefail
# Official Docker apt repository and signing key are configured on this CI base image.
sudo apt update
# INSTALL_DOCKER
sudo systemctl status docker

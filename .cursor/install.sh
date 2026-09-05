#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap for the Elys userbot.
# Installs system libraries, creates a virtualenv and installs Python deps.
set -euo pipefail

cd "$(dirname "$0")/.."

VENV_DIR="${ELYS_VENV_DIR:-.venv}"

echo "==> Installing system packages"
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq
sudo apt-get install -y --no-install-recommends \
	build-essential \
	ffmpeg \
	git \
	imagemagick \
	libcairo2 \
	libffi-dev \
	libjpeg-dev \
	libmagic1 \
	libopenjp2-7 \
	libtiff-dev \
	libwebp-dev \
	libz-dev \
	python3 \
	python3-dev \
	python3-pip \
	python3-venv

echo "==> Creating virtualenv at ${VENV_DIR}"
if [ ! -x "${VENV_DIR}/bin/python" ]; then
	python3 -m venv "${VENV_DIR}"
fi

VENV_PY="${VENV_DIR}/bin/python"

echo "==> Upgrading pip toolchain"
"${VENV_PY}" -m pip install --upgrade --quiet pip setuptools wheel

echo "==> Installing Python requirements"
"${VENV_PY}" -m pip install --upgrade --disable-pip-version-check -r requirements.txt

# Pre-seed the requirements hash so `python -m elys` does not re-install
# dependencies and restart on first boot.
"${VENV_PY}" - <<'PY'
import hashlib
from pathlib import Path

digest = hashlib.sha256(Path("requirements.txt").read_bytes()).hexdigest()
Path(".requirements_hash").write_text(digest)
print(f"==> Seeded .requirements_hash ({digest[:12]}...)")
PY

echo "==> Verifying the userbot boots"
ELYS_NO_GIT=1 "${VENV_PY}" -m elys --no-auth --no-git --no-tty

echo "==> Elys environment ready. Start it with:"
echo "    ${VENV_DIR}/bin/python -m elys --no-git"

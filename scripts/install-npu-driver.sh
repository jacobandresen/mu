#!/usr/bin/env bash
# Install Intel NPU user-space driver for Meteor Lake / Arrow Lake / Lunar Lake.
# Tested on Ubuntu 24.04/26.04 with kernel 6.8+.
# After install, verify with: python3 -c "import openvino as ov; print(ov.Core().available_devices)"

set -euo pipefail

NPU_RELEASE="v1.32.1"
TARBALL="linux-npu-driver-${NPU_RELEASE}.20260422-24767473183-ubuntu2404.tar.gz"
DOWNLOAD_URL="https://github.com/intel/linux-npu-driver/releases/download/${NPU_RELEASE}/${TARBALL}"
LIBZE_URL="https://snapshot.ppa.launchpadcontent.net/kobuk-team/intel-graphics/ubuntu/20260324T100000Z/pool/main/l/level-zero-loader/libze1_1.27.0-1~24.04~ppa2_amd64.deb"

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

# ── 1. Check for Intel NPU hardware ──────────────────────────────────────────
echo "==> Checking for Intel NPU hardware…"
if ! lsmod | grep -q intel_vpu && ! lspci 2>/dev/null | grep -qi "8086:7d1d"; then
    echo "ERROR: No Intel NPU detected (Meteor Lake, Arrow Lake, or Lunar Lake required)." >&2
    exit 1
fi
echo "    NPU detected."

# ── 2. Ensure kernel driver is loaded ────────────────────────────────────────
echo "==> Checking kernel driver (intel_vpu)…"
if ! lsmod | grep -q intel_vpu; then
    echo "    Loading intel_vpu module…"
    sudo modprobe intel_vpu
fi
echo "    intel_vpu loaded."

# ── 3. Download driver package ────────────────────────────────────────────────
echo "==> Downloading Intel NPU driver ${NPU_RELEASE}…"
wget -q --show-progress -O "${WORKDIR}/${TARBALL}" "${DOWNLOAD_URL}"
tar -xf "${WORKDIR}/${TARBALL}" -C "${WORKDIR}"

# ── 4. Install driver DEBs ────────────────────────────────────────────────────
echo "==> Installing NPU driver packages (requires sudo)…"
sudo apt-get install -y "${WORKDIR}"/intel-*.deb

# ── 5. Install Level Zero runtime ─────────────────────────────────────────────
echo "==> Installing Level Zero runtime…"
wget -q --show-progress -O "${WORKDIR}/libze1.deb" "${LIBZE_URL}"
sudo apt-get install -y "${WORKDIR}/libze1.deb" || {
    echo "    libze1 conflict — removing old level-zero and retrying…"
    sudo dpkg --purge --force-remove-reinstreq level-zero level-zero-devel 2>/dev/null || true
    sudo apt-get install -y "${WORKDIR}/libze1.deb"
}

# ── 6. Add user to render group ───────────────────────────────────────────────
if ! id -nG "$USER" | grep -qw render; then
    echo "==> Adding ${USER} to the render group…"
    sudo gpasswd -a "${USER}" render
    echo "    Done. You must log out and back in (or run 'newgrp render') for this to take effect."
else
    echo "==> ${USER} is already in the render group."
fi

# ── 7. Verify ─────────────────────────────────────────────────────────────────
echo ""
echo "==> Verifying device node…"
if ls /dev/accel/accel0 &>/dev/null; then
    echo "    /dev/accel/accel0 present."
else
    echo "    WARNING: /dev/accel/accel0 not found. Try: sudo modprobe intel_vpu"
fi

echo ""
echo "✅ Intel NPU driver installed."
echo ""
echo "Next steps:"
echo "  1. Run 'newgrp render' or log out/in to activate group membership."
echo "  2. Verify OpenVINO sees the NPU:"
echo "       python3 -c \"import openvino as ov; print(ov.Core().available_devices)\""
echo "     Expected: ['CPU', 'NPU']"
echo "  3. Use it with mu:"
echo "       mu serve <model_dir> --device NPU"

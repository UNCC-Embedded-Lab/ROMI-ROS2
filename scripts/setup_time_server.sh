#!/usr/bin/env bash
###############################################################################
# setup_time_server.sh — make the laptop an NTP time server for the robot Pi so
# the Pi corrects its own clock automatically. An alternative to the manual
# one-shot push in sync_pi_clock.sh for day-to-day use (that script stays as a
# simpler fallback and is the primary supported workflow for this repo).
#
# RUN THIS ON THE LAPTOP HOST (not inside the dev container). The container uses
# --net=host, so an NTP server on the host is reachable by the Pi on UDP 123.
#
# Two sides are configured:
#   Laptop -> chrony NTP server. Serves the robot subnet and works even when the
#             laptop itself has no internet (`local stratum 10`).
#   Pi     -> its existing NTP client (chrony if present, else systemd-timesyncd)
#             is pointed at the laptop — no package install needed on the offline
#             Pi.
#
# This script does NOT install, gate, or restart any ROS/robot systemd service.
# It only configures NTP. Launch/relaunch romi_robot.launch.py yourself.
#
# Usage:
#   ./scripts/setup_time_server.sh                 # configure both sides
#   ./scripts/setup_time_server.sh --server-ip 192.168.4.2
#   ./scripts/setup_time_server.sh --no-pi         # only set up the laptop server
#
# Needs sudo on the laptop (local) and on the Pi (over SSH).
###############################################################################

set -euo pipefail

PI_USER="${PI_USER:-student}"
PI_HOST="${PI_HOST:-192.168.4.1}"
SUBNET="${SUBNET:-192.168.4.0/24}"
SERVER_IP="${SERVER_IP:-}"                 # auto-detected on the subnet if empty
CONFIGURE_PI="true"

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Configure the laptop as an NTP server and point the robot Pi's NTP client at it.

Options:
  --host HOST      Pi host.                 Default: ${PI_HOST}
  --user USER      SSH user on the Pi.      Default: ${PI_USER}
  --subnet CIDR    Robot subnet to serve.   Default: ${SUBNET}
  --server-ip IP   Laptop IP the Pi points at (default: auto-detect on subnet).
  --no-pi          Configure only the laptop chrony server, not the Pi.
  -h, --help       Show this help.

Environment overrides:
  PI_USER, PI_HOST, SUBNET, SERVER_IP
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)       PI_HOST="$2"; shift 2 ;;
    --user)       PI_USER="$2"; shift 2 ;;
    --subnet)     SUBNET="$2"; shift 2 ;;
    --server-ip)  SERVER_IP="$2"; shift 2 ;;
    --no-pi)      CONFIGURE_PI="false"; shift ;;
    -h|--help)    usage; exit 0 ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

# --------------------------------------------------------------------------- #
# 1) Laptop: install and configure chrony as an NTP server for the robot subnet
# --------------------------------------------------------------------------- #
echo "== Laptop: configuring chrony NTP server =="

if ! command -v chronyd >/dev/null 2>&1; then
  echo "Installing chrony..."
  sudo apt-get update
  sudo apt-get install -y chrony
fi

# Locate the main config so we can guarantee the drop-in directory is included.
CHRONY_CONF=/etc/chrony/chrony.conf
[[ -f "$CHRONY_CONF" ]] || CHRONY_CONF=/etc/chrony.conf
CONFDIR=/etc/chrony/conf.d

sudo mkdir -p "$CONFDIR"

# `local stratum 10` makes chrony serve its own clock as a valid time source
# even when the laptop has no upstream NTP (the offline-lab case). `allow`
# permits the robot subnet to query us.
printf '%s\n' \
  "# Managed by scripts/setup_time_server.sh — do not edit by hand." \
  "allow ${SUBNET}" \
  "local stratum 10" \
  | sudo tee "$CONFDIR/romi.conf" >/dev/null

# Older chrony.conf files may not pull in conf.d; add the include if missing.
if ! grep -qE '^[[:space:]]*confdir[[:space:]].*conf\.d' "$CHRONY_CONF" 2>/dev/null; then
  echo "confdir ${CONFDIR}" | sudo tee -a "$CHRONY_CONF" >/dev/null
fi

# Service is `chrony` on Debian/Ubuntu, `chronyd` elsewhere.
sudo systemctl enable chrony >/dev/null 2>&1 || sudo systemctl enable chronyd >/dev/null 2>&1 || true
sudo systemctl restart chrony 2>/dev/null || sudo systemctl restart chronyd

# Open the firewall for NTP from the robot subnet only, if ufw is active.
if command -v ufw >/dev/null 2>&1 && sudo ufw status 2>/dev/null | grep -q "Status: active"; then
  sudo ufw allow from "${SUBNET}" to any port 123 proto udp || true
fi

echo "  chrony serving NTP to ${SUBNET}"

# --------------------------------------------------------------------------- #
# 2) Determine the laptop IP the Pi should point at (must be on the subnet).
# --------------------------------------------------------------------------- #
if [[ -z "$SERVER_IP" ]]; then
  BASE="${SUBNET%/*}"          # 192.168.4.0
  PREFIX="${BASE%.*}"          # 192.168.4
  SERVER_IP="$(ip -4 -o addr show 2>/dev/null | awk '{print $4}' | cut -d/ -f1 \
                | grep -E "^${PREFIX//./\\.}\." | head -n1 || true)"
fi

if [[ -z "$SERVER_IP" ]]; then
  echo "ERROR: could not find a laptop IP on ${SUBNET}." >&2
  echo "       Connect to the robot's WiFi, or pass --server-ip <addr>." >&2
  exit 1
fi
echo "  laptop NTP address: ${SERVER_IP}"

if [[ "$CONFIGURE_PI" != "true" ]]; then
  echo "Laptop server ready. Skipping Pi configuration (--no-pi)."
  echo "Point the Pi's systemd-timesyncd at ${SERVER_IP} to finish."
  exit 0
fi

# --------------------------------------------------------------------------- #
# 3) Pi: point its NTP client at the laptop. No package install — the Pi
#        already has either chrony or systemd-timesyncd built in.
# --------------------------------------------------------------------------- #
REMOTE="${PI_USER}@${PI_HOST}"

if ! command -v ssh >/dev/null 2>&1; then
  echo "Missing required command: ssh" >&2
  exit 127
fi

# Reuse one SSH connection so a password-auth Pi prompts only once.
SSH_CTL="$(mktemp -u "${TMPDIR:-/tmp}/romi_ssh_ctl.XXXXXX")"
SSH_OPTS=(-o ControlMaster=auto -o "ControlPath=${SSH_CTL}" -o ControlPersist=30)
cleanup() {
  ssh -O exit -o "ControlPath=${SSH_CTL}" "$REMOTE" 2>/dev/null || true
  rm -f "$SSH_CTL"
}
trap cleanup EXIT

echo "== Pi: pointing systemd-timesyncd at ${SERVER_IP} =="
if ! ssh "${SSH_OPTS[@]}" -o ConnectTimeout=5 "$REMOTE" true; then
  echo "Cannot reach ${REMOTE}. Are you connected to the robot's WiFi?" >&2
  exit 1
fi

# The remote body runs under sudo, which needs a real terminal for its prompt.
# We pass it as a base64 argument (not on stdin) so `ssh -t` can allocate a PTY.
REMOTE_BODY="$(cat <<'EOF'
set -euo pipefail

if command -v chronyd >/dev/null 2>&1; then
  # The Pi already runs chrony (a better NTP client than timesyncd, and it masks
  # timesyncd). Point chrony at the laptop and let it STEP the clock for a large
  # offset — essential to correct the no-RTC boot offset quickly.
  sudo mkdir -p /etc/chrony/conf.d
  printf '%s\n' \
    "# Managed by scripts/setup_time_server.sh — do not edit by hand." \
    "server ${SERVER_IP} iburst" \
    "makestep 1 3" \
    | sudo tee /etc/chrony/conf.d/romi.conf >/dev/null

  # Ensure chrony.conf pulls in conf.d (older configs may not).
  CHRONY_CONF=/etc/chrony/chrony.conf
  [ -f "$CHRONY_CONF" ] || CHRONY_CONF=/etc/chrony.conf
  if ! grep -qE '^[[:space:]]*confdir[[:space:]].*conf\.d' "$CHRONY_CONF" 2>/dev/null; then
    echo "confdir /etc/chrony/conf.d" | sudo tee -a "$CHRONY_CONF" >/dev/null
  fi

  sudo systemctl enable chrony >/dev/null 2>&1 || sudo systemctl enable chronyd >/dev/null 2>&1 || true
  sudo systemctl restart chrony 2>/dev/null || sudo systemctl restart chronyd
  echo "  chrony on the Pi now syncs from ${SERVER_IP}"
else
  # No chrony: use the built-in systemd-timesyncd (unmask it if it was masked).
  sudo systemctl unmask systemd-timesyncd >/dev/null 2>&1 || true
  sudo mkdir -p /etc/systemd/timesync.conf.d
  printf '%s\n' '[Time]' "NTP=${SERVER_IP}" \
    | sudo tee /etc/systemd/timesync.conf.d/romi.conf >/dev/null
  sudo timedatectl set-ntp true
  sudo systemctl enable systemd-timesyncd >/dev/null 2>&1 || true
  sudo systemctl restart systemd-timesyncd
  echo "  timesyncd on the Pi now syncs from ${SERVER_IP}"
fi
EOF
)"

REMOTE_B64="$(printf '%s' "$REMOTE_BODY" | base64 | tr -d '\n')"

REMOTE_CMD="echo '${REMOTE_B64}' | base64 -d |"
REMOTE_CMD="${REMOTE_CMD} SERVER_IP='${SERVER_IP}'"
REMOTE_CMD="${REMOTE_CMD} bash"

ssh -t "${SSH_OPTS[@]}" "$REMOTE" "$REMOTE_CMD"

echo
echo "Done. The Pi will sync from the laptop automatically."
echo "Check on the laptop:  chronyc clients        (Pi should appear after it polls)"
echo "Check on the Pi:      timedatectl status     (System clock synchronized: yes)"

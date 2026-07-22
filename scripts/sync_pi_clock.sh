#!/usr/bin/env bash
###############################################################################
# sync_pi_clock.sh — push THIS laptop's clock onto the robot's Raspberry Pi.
#
# The Pi runs on an isolated robot WiFi with no internet and (typically) no
# RTC battery, so its wall clock drifts every boot. ROS 2 relies on message
# timestamps and TF being roughly aligned across machines; a skewed Pi clock
# causes "message filter dropping message" / extrapolation-into-the-future TF
# errors and makes AMCL and the nav stack misbehave.
#
# This script treats the laptop as the reference clock and SSHes into the Pi to
# set its time to match. Run it once after connecting to the robot's WiFi (and
# again if you leave the Pi powered for a long session).
#
# If the robot stack is started by a systemd service at boot (see
# scripts/install_robot_service.sh), those nodes latched onto the Pi's wrong
# boot-time clock. Simply stepping the clock underneath them causes TF jumps,
# so this script also restarts that service afterwards so the ROS nodes come
# back up with the corrected time. The restart is skipped gracefully if the
# service is not installed.
#
# Usage:
#   ./scripts/sync_pi_clock.sh                 # sync + restart robot service
#   ./scripts/sync_pi_clock.sh --host 10.0.0.5 --user pi
#   ./scripts/sync_pi_clock.sh --no-restart    # sync clock only
#   PI_HOST=192.168.4.1 ./scripts/sync_pi_clock.sh --hwclock
#
# Requires: passwordless SSH to the Pi is convenient but not required (you may
# be prompted for the SSH and/or sudo password). Setting the clock needs sudo
# on the Pi.
###############################################################################

set -euo pipefail

# Defaults match the other ROMI scripts (see scripts/sync_to_pi.sh).
PI_USER="${PI_USER:-student}"
PI_HOST="${PI_HOST:-192.168.4.1}"
WRITE_HWCLOCK="false"
RESTART_SERVICE="${RESTART_SERVICE:-romi_robot.service}"
DO_RESTART="true"

usage() {
  cat <<EOF
Usage: $(basename "$0") [--host HOST] [--user USER] [--hwclock] [--service NAME] [--no-restart]

Push this laptop's current time onto the robot's Raspberry Pi over SSH, then
restart the robot systemd service so its ROS nodes use the corrected time.

Options:
  --host HOST     Override the Pi host.  Default: ${PI_HOST}
  --user USER     Override the SSH user. Default: ${PI_USER}
  --hwclock       Also write the synced time to the Pi's hardware RTC (best
                  effort; only useful if the Pi actually has an RTC module).
  --service NAME  Robot service to restart after sync. Default: ${RESTART_SERVICE}
  --no-restart    Sync the clock only; do not restart any service.
  -h, --help      Show this help.

Environment overrides:
  PI_USER, PI_HOST, RESTART_SERVICE
EOF
}

while [[ $# -gt 0 ]]; do
  # Simple manual flag parsing to keep the script dependency-free.
  case "$1" in
    --host)
      PI_HOST="$2"
      shift 2
      ;;
    --user)
      PI_USER="$2"
      shift 2
      ;;
    --hwclock)
      WRITE_HWCLOCK="true"
      shift
      ;;
    --service)
      RESTART_SERVICE="$2"
      shift 2
      ;;
    --no-restart)
      DO_RESTART="false"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

# Fail early with a clear message if SSH is missing.
if ! command -v ssh >/dev/null 2>&1; then
  echo "Missing required command: ssh" >&2
  exit 127
fi

REMOTE="${PI_USER}@${PI_HOST}"

# Confirm the Pi is reachable before we try to change its clock, so failures
# produce an obvious "can't connect" message instead of a cryptic ssh error.
echo "Checking connectivity to ${REMOTE}..."
if ! ssh -o ConnectTimeout=5 -o BatchMode=no "$REMOTE" true; then
  echo "Cannot reach ${REMOTE}. Are you connected to the robot's WiFi?" >&2
  exit 1
fi

echo "Laptop time (UTC):  $(date -u '+%Y-%m-%d %H:%M:%S.%3N %Z')"
echo "Pi time before:     $(ssh "$REMOTE" 'date -u "+%Y-%m-%d %H:%M:%S.%3N %Z"')"

# Capture the laptop's time with sub-second precision as late as possible, then
# set it on the Pi in the same SSH invocation. The residual skew is roughly the
# SSH round-trip/auth latency (sub-second with key-based auth), which is well
# within ROS 2's tolerance. `set-ntp false` prevents systemd-timesyncd from
# immediately overwriting the value we just set; on an offline Pi NTP can never
# succeed anyway, so disabling it is safe.
LAPTOP_EPOCH="$(date -u +%s.%N)"

echo "Setting Pi clock..."
ssh -t "$REMOTE" \
  LAPTOP_EPOCH="$LAPTOP_EPOCH" \
  WRITE_HWCLOCK="$WRITE_HWCLOCK" \
  DO_RESTART="$DO_RESTART" \
  RESTART_SERVICE="$RESTART_SERVICE" \
  'bash -s' <<'EOF'
set -euo pipefail

# Stop timesyncd (if present) from racing us; ignore failures on minimal images.
sudo timedatectl set-ntp false >/dev/null 2>&1 || true

# GNU date on Raspberry Pi OS accepts an @<epoch.fraction> argument.
sudo date -u -s "@${LAPTOP_EPOCH}" >/dev/null

if [[ "${WRITE_HWCLOCK}" == "true" ]]; then
  # Persist to the hardware RTC if one exists; harmless best-effort otherwise.
  sudo hwclock --systohc >/dev/null 2>&1 \
    && echo "  wrote time to hardware RTC" \
    || echo "  no writable RTC found (skipping hwclock)"
fi

# Restart the robot service so nodes that booted with the wrong clock restart
# with the corrected time. `systemctl cat` returns non-zero when the unit does
# not exist, so this stays robust whether or not the service is installed.
if [[ "${DO_RESTART}" != "true" ]]; then
  echo "  service restart skipped (--no-restart)"
elif systemctl cat "${RESTART_SERVICE}" >/dev/null 2>&1; then
  echo "  restarting ${RESTART_SERVICE} so ROS nodes pick up the new time..."
  sudo systemctl restart "${RESTART_SERVICE}"
  echo "  ${RESTART_SERVICE} restarted"
else
  echo "  ${RESTART_SERVICE} not installed; skipping restart"
fi
EOF

echo "Pi time after:      $(ssh "$REMOTE" 'date -u "+%Y-%m-%d %H:%M:%S.%3N %Z"')"
echo "Clock sync complete."

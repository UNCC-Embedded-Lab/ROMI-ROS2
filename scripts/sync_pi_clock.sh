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
INSTALL_SUDOERS="false"

# Max tolerated laptop<->Pi offset (seconds) after syncing. ROS 2 TF cares about
# sub-second alignment, but SSH round-trip and 1-second `date` granularity mean
# a small residual is normal; anything larger indicates the set did not take.
MAX_OFFSET_SEC="${MAX_OFFSET_SEC:-2}"

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
  --install-sudoers
                  One-time setup: install a scoped /etc/sudoers.d rule so the
                  clock commands run without a password. This removes the sudo
                  prompt whose typing delay otherwise skews the synced time.
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
    --install-sudoers)
      INSTALL_SUDOERS="true"
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

# Reuse ONE SSH connection for every call below. On a password-auth Pi this
# means you type the SSH password just once instead of for each command.
SSH_CTL="$(mktemp -u "${TMPDIR:-/tmp}/romi_ssh_ctl.XXXXXX")"
SSH_OPTS=(-o ControlMaster=auto -o "ControlPath=${SSH_CTL}" -o ControlPersist=30)

cleanup() {
  # Close the shared master connection and remove its socket on exit.
  ssh -O exit -o "ControlPath=${SSH_CTL}" "$REMOTE" 2>/dev/null || true
  rm -f "$SSH_CTL"
}
trap cleanup EXIT

# Confirm the Pi is reachable before we try to change its clock, so failures
# produce an obvious "can't connect" message instead of a cryptic ssh error.
# This first call also establishes the shared connection (and prompts for the
# SSH password once, if key-based auth is not set up).
echo "Checking connectivity to ${REMOTE}..."
if ! ssh "${SSH_OPTS[@]}" -o ConnectTimeout=5 "$REMOTE" true; then
  echo "Cannot reach ${REMOTE}. Are you connected to the robot's WiFi?" >&2
  exit 1
fi

# One-time setup: install a scoped passwordless-sudo rule so later syncs are not
# skewed by sudo password-entry delay. This step itself prompts for the sudo
# password once. Scoped to clock-related commands only.
if [[ "$INSTALL_SUDOERS" == "true" ]]; then
  echo "Installing passwordless-sudo rule for clock commands on ${REMOTE}..."

  TS_CLOCK=/var/lib/systemd/timesync/clock
  TS_DIR="$(dirname "$TS_CLOCK")"
  SUDOERS_CONTENT="# Managed by scripts/sync_pi_clock.sh --install-sudoers
# Lets ${PI_USER} correct the system clock without a password so time sync is
# not skewed by password-entry latency. Scoped to clock-related commands only.
Cmnd_Alias ROMI_CLOCK = /usr/bin/date, /bin/date, /usr/bin/timedatectl, /bin/timedatectl, /usr/sbin/hwclock, /sbin/hwclock, /usr/sbin/fake-hwclock, /usr/bin/fake-hwclock, /usr/bin/touch ${TS_CLOCK}, /bin/touch ${TS_CLOCK}, /usr/bin/mkdir -p ${TS_DIR}, /bin/mkdir -p ${TS_DIR}, /usr/bin/systemctl restart ${RESTART_SERVICE}, /bin/systemctl restart ${RESTART_SERVICE}
${PI_USER} ALL=(root) NOPASSWD: ROMI_CLOCK
"
  SUDOERS_B64="$(printf '%s' "$SUDOERS_CONTENT" | base64 | tr -d '\n')"

  # Validate the syntax on a temp file BEFORE installing to the live location.
  # An invalid file under /etc/sudoers.d would break sudo entirely, so we never
  # place it there until `visudo -c` confirms it parses.
  INSTALL_BODY="$(cat <<'EOF'
set -euo pipefail
TMP="$(mktemp)"
printf '%s' "$SUDOERS_B64" | base64 -d > "$TMP"
if sudo visudo -cf "$TMP" >/dev/null; then
  sudo install -m 0440 -o root -g root "$TMP" /etc/sudoers.d/romi-clock
  echo "  installed /etc/sudoers.d/romi-clock (clock commands are now passwordless)"
else
  echo "  ERROR: generated sudoers is invalid; not installing" >&2
  rm -f "$TMP"
  exit 1
fi
rm -f "$TMP"
EOF
)"
  INSTALL_B64="$(printf '%s' "$INSTALL_BODY" | base64 | tr -d '\n')"

  ssh -t "${SSH_OPTS[@]}" "$REMOTE" \
    "echo '${INSTALL_B64}' | base64 -d | SUDOERS_B64='${SUDOERS_B64}' bash"

  echo "Done. Re-run without --install-sudoers to sync the clock (no sudo prompt)."
  exit 0
fi

echo "Laptop time (UTC):  $(date -u '+%Y-%m-%d %H:%M:%S.%3N %Z')"
echo "Pi time before:     $(ssh "${SSH_OPTS[@]}" "$REMOTE" 'date -u "+%Y-%m-%d %H:%M:%S.%3N %Z"')"

# Capture the laptop's time with sub-second precision as late as possible, then
# set it on the Pi in the same SSH invocation. The residual skew is roughly the
# SSH round-trip/auth latency (sub-second with key-based auth), which is well
# within ROS 2's tolerance. We deliberately do NOT disable timesyncd: on an
# offline robot network it can never reach a server (so it can't overwrite our
# value), and leaving it enabled is what restores the saved clock forward at the
# next boot.
LAPTOP_EPOCH="$(date -u +%s.%N)"

echo "Setting Pi clock..."

# sudo on the Pi needs a real terminal to prompt for its password. If we piped
# the script in on ssh's stdin (a here-doc), ssh would refuse to allocate a PTY
# ("stdin is not a terminal") and sudo would fail. So pass the script as a
# base64 argument, let `ssh -t` allocate a PTY for the sudo prompt, and have the
# remote bash read the decoded script from the pipe instead of stdin.
REMOTE_BODY="$(cat <<'EOF'
set -euo pipefail

# Set the clock first. GNU date (Raspberry Pi OS / Ubuntu) accepts an
# @<epoch.fraction> argument. On an isolated offline network timesyncd cannot
# reach a server, so it will not overwrite this value.
sudo date -u -s "@${LAPTOP_EPOCH}" >/dev/null

if [[ "${WRITE_HWCLOCK}" == "true" ]]; then
  # Persist to the hardware RTC if one exists; harmless best-effort otherwise.
  sudo hwclock --systohc >/dev/null 2>&1 \
    && echo "  wrote time to hardware RTC" \
    || echo "  no writable RTC found (skipping hwclock)"
fi

# --- Make the corrected time survive a reboot (the Pi has no RTC) ---
# Which store the OS consults at boot varies, and a stale store is exactly what
# left this Pi frozen at an old date, so update EVERY store we can find.
PERSISTED="false"

# (1) Raspberry Pi OS: fake-hwclock replays a saved timestamp at boot.
if command -v fake-hwclock >/dev/null 2>&1; then
  if sudo fake-hwclock save >/dev/null 2>&1; then
    echo "  persisted corrected time to fake-hwclock"
    PERSISTED="true"
  fi
fi

# (2) systemd default (Ubuntu): at boot systemd-timesyncd advances the clock to
# the mtime of its saved clock file. Refresh that mtime to 'now' and ensure the
# service is enabled so the bump actually runs next boot. Offline this only ever
# moves the clock forward, never backward, so enabling it is safe.
TS_CLOCK=/var/lib/systemd/timesync/clock
if test -e "${TS_CLOCK}" || test -d "$(dirname "${TS_CLOCK}")"; then
  sudo mkdir -p "$(dirname "${TS_CLOCK}")" >/dev/null 2>&1 || true
  if sudo touch "${TS_CLOCK}" >/dev/null 2>&1; then
    sudo timedatectl set-ntp true >/dev/null 2>&1 || true
    echo "  refreshed systemd-timesyncd clock file (survives reboot)"
    PERSISTED="true"
  fi
fi

if [[ "${PERSISTED}" != "true" ]]; then
  echo "  WARNING: no reboot-persistent time store found; clock will drift on reboot"
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
)"

REMOTE_B64="$(printf '%s' "$REMOTE_BODY" | base64 | tr -d '\n')"

# Build the remote command: decode the script and run it under bash, with the
# needed values injected as environment variables. base64 output is quoting-safe
# so this survives ssh's argument handling intact.
REMOTE_CMD="echo '${REMOTE_B64}' | base64 -d |"
REMOTE_CMD="${REMOTE_CMD} LAPTOP_EPOCH='${LAPTOP_EPOCH}'"
REMOTE_CMD="${REMOTE_CMD} WRITE_HWCLOCK='${WRITE_HWCLOCK}'"
REMOTE_CMD="${REMOTE_CMD} DO_RESTART='${DO_RESTART}'"
REMOTE_CMD="${REMOTE_CMD} RESTART_SERVICE='${RESTART_SERVICE}'"
REMOTE_CMD="${REMOTE_CMD} bash"

ssh -t "${SSH_OPTS[@]}" "$REMOTE" "$REMOTE_CMD"

echo "Pi time after:      $(ssh "${SSH_OPTS[@]}" "$REMOTE" 'date -u "+%Y-%m-%d %H:%M:%S.%3N %Z"')"

# Read the Pi clock back and confirm the correction actually took. Without this,
# a silently failed `date` (e.g. sudo denied, or a service that reset the clock)
# looks like success and only surfaces later as nav2 "Transform data too old"
# errors. Grab both epochs close together; the residual should be within
# MAX_OFFSET_SEC once accounting for SSH latency and 1s granularity.
echo "Verifying clock offset..."
PI_EPOCH_AFTER="$(ssh "${SSH_OPTS[@]}" "$REMOTE" 'date -u +%s')"
LAPTOP_EPOCH_AFTER="$(date -u +%s)"
OFFSET=$(( LAPTOP_EPOCH_AFTER - PI_EPOCH_AFTER ))
ABS_OFFSET="${OFFSET#-}"

if (( ABS_OFFSET > MAX_OFFSET_SEC )); then
  echo "ERROR: Pi clock is still off by ${OFFSET}s (limit ${MAX_OFFSET_SEC}s)." >&2
  echo "       The correction did not take. Check that the SSH user can sudo" >&2
  echo "       without a hang, and that nothing (e.g. fake-hwclock/timesyncd)" >&2
  echo "       is resetting the clock. ROS timestamps will be wrong until fixed." >&2
  exit 1
fi

echo "Clock verified: laptop-Pi offset ${OFFSET}s (within ${MAX_OFFSET_SEC}s)."
echo "Clock sync complete."

#!/usr/bin/env bash
###############################################################################
# install_robot_service.sh — install the romi_robot systemd service that
# auto-launches romi_robot.launch.py on the Pi at boot.
#
# Bundles the manual `tee /etc/systemd/system/... + daemon-reload + enable +
# start` steps into one idempotent command. Re-running it updates the unit
# file and reloads/restarts the service, so it is safe to run repeatedly.
#
# By default it targets the Pi over SSH (matching scripts/sync_to_pi.sh);
# pass --local to install directly when you are already on the Pi.
#
# Usage:
#   ./scripts/install_robot_service.sh                 # over SSH to the Pi
#   ./scripts/install_robot_service.sh --local         # run on the Pi itself
#   ./scripts/install_robot_service.sh --host 10.0.0.5 --user pi
#
# Setting up the unit needs sudo on the Pi (you may be prompted for a password).
###############################################################################

set -euo pipefail

# Defaults match the other ROMI scripts (see scripts/sync_to_pi.sh).
PI_USER="${PI_USER:-student}"
PI_HOST="${PI_HOST:-192.168.4.1}"

# Service definition — every field is overridable so the unit stays in sync
# with non-default workspaces / users without editing this script.
SERVICE_NAME="${SERVICE_NAME:-romi_robot.service}"
SERVICE_USER="${SERVICE_USER:-student}"
ROS_DISTRO_NAME="${ROS_DISTRO_NAME:-humble}"
REMOTE_WORKSPACE="${REMOTE_WORKSPACE:-/home/${SERVICE_USER}/ros2_ws}"
LAUNCH_CMD="${LAUNCH_CMD:-ros2 launch romi_base romi_robot.launch.py}"

RUN_LOCAL="false"
DO_ENABLE="true"
DO_START="true"

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Install/refresh the ${SERVICE_NAME} systemd unit that launches the Romi robot
stack at boot.

Options:
  --host HOST         Pi host (SSH mode).        Default: ${PI_HOST}
  --user USER         SSH user (SSH mode).       Default: ${PI_USER}
  --local             Install on this machine (no SSH); use when on the Pi.
  --service NAME      Unit file name.            Default: ${SERVICE_NAME}
  --service-user USER User the service runs as.  Default: ${SERVICE_USER}
  --ros-distro DISTRO ROS distro to source.      Default: ${ROS_DISTRO_NAME}
  --workspace PATH    ROS 2 workspace on the Pi. Default: ${REMOTE_WORKSPACE}
  --launch CMD        Launch command.            Default: ${LAUNCH_CMD}
  --no-enable         Do not enable the service at boot.
  --no-start          Do not start the service now.
  -h, --help          Show this help.

Environment overrides:
  PI_USER, PI_HOST, SERVICE_NAME, SERVICE_USER, ROS_DISTRO_NAME,
  REMOTE_WORKSPACE, LAUNCH_CMD
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)         PI_HOST="$2"; shift 2 ;;
    --user)         PI_USER="$2"; shift 2 ;;
    --local)        RUN_LOCAL="true"; shift ;;
    --service)      SERVICE_NAME="$2"; shift 2 ;;
    --service-user) SERVICE_USER="$2"; shift 2 ;;
    --ros-distro)   ROS_DISTRO_NAME="$2"; shift 2 ;;
    --workspace)    REMOTE_WORKSPACE="$2"; shift 2 ;;
    --launch)       LAUNCH_CMD="$2"; shift 2 ;;
    --no-enable)    DO_ENABLE="false"; shift ;;
    --no-start)     DO_START="false"; shift ;;
    -h|--help)      usage; exit 0 ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

REMOTE="${PI_USER}@${PI_HOST}"

if [[ "$RUN_LOCAL" != "true" ]]; then
  if ! command -v ssh >/dev/null 2>&1; then
    echo "Missing required command: ssh" >&2
    exit 127
  fi
  echo "Checking connectivity to ${REMOTE}..."
  if ! ssh -o ConnectTimeout=5 "$REMOTE" true; then
    echo "Cannot reach ${REMOTE}. Are you connected to the robot's WiFi?" >&2
    exit 1
  fi
fi

# Build the unit file content. The delimiter is unquoted so the ${...} fields
# above are expanded here; the single quotes inside ExecStart are preserved
# literally, which is exactly what systemd needs.
UNIT_CONTENT="$(cat <<UNITEOF
[Unit]
Description=Romi robot stack (base controller + RPLidar)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
ExecStart=/bin/bash -lc 'source /opt/ros/${ROS_DISTRO_NAME}/setup.bash && source ${REMOTE_WORKSPACE}/install/setup.bash && ${LAUNCH_CMD}'
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
UNITEOF
)"

# Assemble the privileged steps into one command so we only prompt for sudo
# once. `restart` (not `start`) makes re-runs pick up unit changes idempotently.
MANAGE_CMDS="systemctl daemon-reload"
[[ "$DO_ENABLE" == "true" ]] && MANAGE_CMDS="${MANAGE_CMDS} && systemctl enable ${SERVICE_NAME}"
[[ "$DO_START"  == "true" ]] && MANAGE_CMDS="${MANAGE_CMDS} && systemctl restart ${SERVICE_NAME}"

UNIT_PATH="/etc/systemd/system/${SERVICE_NAME}"

if [[ "$RUN_LOCAL" == "true" ]]; then
  echo "Writing ${UNIT_PATH} (local)..."
  printf '%s\n' "$UNIT_CONTENT" | sudo tee "$UNIT_PATH" >/dev/null
  echo "Applying: ${MANAGE_CMDS}"
  sudo bash -c "$MANAGE_CMDS"
  echo "Service status:"
  systemctl --no-pager --full status "$SERVICE_NAME" 2>/dev/null | head -n 5 || true
else
  echo "Writing ${UNIT_PATH} on ${REMOTE}..."
  printf '%s\n' "$UNIT_CONTENT" | ssh "$REMOTE" "sudo tee ${UNIT_PATH} >/dev/null"
  echo "Applying on ${REMOTE}: ${MANAGE_CMDS}"
  ssh -t "$REMOTE" "sudo bash -c '${MANAGE_CMDS}'"
  echo "Service status:"
  ssh "$REMOTE" "systemctl --no-pager --full status ${SERVICE_NAME} 2>/dev/null | head -n 5" || true
fi

echo "Done. ${SERVICE_NAME} installed."

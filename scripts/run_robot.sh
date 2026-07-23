#!/usr/bin/env bash
###############################################################################
# run_robot.sh — SSH to the Pi and run romi_robot.launch.py in the foreground.
#
# This runs INTERACTIVELY, on purpose -- it is not a background service and
# does not auto-restart. Press Ctrl-C in this terminal to stop: the SIGINT is
# forwarded through the SSH PTY to `ros2 launch`, which shuts its nodes down
# cleanly (motors included) instead of an abrupt kill.
#
# We deliberately do NOT install this as a systemd service: an earlier attempt
# at auto-launching the robot stack at boot, combined with a clock-sync script
# stepping the system clock while the control loop was already running, caused
# the wheels to spin unexpectedly. Keep this manual and foreground.
#
# Usage:
#   ./scripts/run_robot.sh
#   ./scripts/run_robot.sh --host 10.0.0.5 --user pi
#   ./scripts/run_robot.sh use_lidar:=false lidar_serial_port:=/dev/ttyUSB0
#     (any unrecognized args are passed through to `ros2 launch` as-is)
###############################################################################

set -euo pipefail

PI_USER="${PI_USER:-student}"
PI_HOST="${PI_HOST:-192.168.4.1}"
ROS_DISTRO_NAME="${ROS_DISTRO_NAME:-humble}"
REMOTE_WORKSPACE="${REMOTE_WORKSPACE:-/home/${PI_USER}/ros2_ws}"
LAUNCH_CMD="${LAUNCH_CMD:-ros2 launch romi_base romi_robot.launch.py}"

usage() {
  cat <<EOF
Usage: $(basename "$0") [--host HOST] [--user USER] [--workspace PATH] [--ros-distro DISTRO] [--launch CMD] [launch args...]

SSH to the robot Pi and run romi_robot.launch.py in the foreground. Ctrl-C
stops it cleanly. Not a service -- this only runs while the terminal is open.

Options:
  --host HOST         Pi host.                  Default: ${PI_HOST}
  --user USER         SSH user.                  Default: ${PI_USER}
  --workspace PATH    ROS 2 workspace on the Pi. Default: ${REMOTE_WORKSPACE}
  --ros-distro DISTRO ROS distro to source.       Default: ${ROS_DISTRO_NAME}
  --launch CMD        Launch command to run.     Default: ${LAUNCH_CMD}
  -h, --help          Show this help.

Any other arguments (e.g. use_lidar:=false) are appended to the launch command
and passed through to 'ros2 launch' as launch configuration overrides.

Environment overrides:
  PI_USER, PI_HOST, REMOTE_WORKSPACE, ROS_DISTRO_NAME, LAUNCH_CMD
EOF
}

EXTRA_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      PI_HOST="$2"
      shift 2
      ;;
    --user)
      PI_USER="$2"
      shift 2
      ;;
    --workspace)
      REMOTE_WORKSPACE="$2"
      shift 2
      ;;
    --ros-distro)
      ROS_DISTRO_NAME="$2"
      shift 2
      ;;
    --launch)
      LAUNCH_CMD="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      # Anything else (e.g. use_lidar:=false) is a launch argument passthrough.
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

if ! command -v ssh >/dev/null 2>&1; then
  echo "Missing required command: ssh" >&2
  exit 127
fi

REMOTE="${PI_USER}@${PI_HOST}"

echo "Checking connectivity to ${REMOTE}..."
if ! ssh -o ConnectTimeout=5 "$REMOTE" true; then
  echo "Cannot reach ${REMOTE}. Are you connected to the robot's WiFi?" >&2
  exit 1
fi

FULL_LAUNCH_CMD="$LAUNCH_CMD"
if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
  FULL_LAUNCH_CMD="${FULL_LAUNCH_CMD} ${EXTRA_ARGS[*]}"
fi

echo "Launching on ${REMOTE}: ${FULL_LAUNCH_CMD}"
echo "Press Ctrl-C to stop the robot stack."

# -t allocates a PTY so Ctrl-C here delivers a real SIGINT to the remote
# process group, letting `ros2 launch` shut its nodes down gracefully instead
# of the connection just dropping and leaving things in an unknown state.
ssh -t "$REMOTE" \
  "bash -lc 'source /opt/ros/${ROS_DISTRO_NAME}/setup.bash && source ${REMOTE_WORKSPACE}/install/setup.bash && ${FULL_LAUNCH_CMD}'"

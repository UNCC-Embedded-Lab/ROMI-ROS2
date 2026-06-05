#!/usr/bin/env bash

set -euo pipefail

# Defaults are tuned for a typical lab setup; each value can be overridden
# by either CLI flags or environment variables.
PI_USER="${PI_USER:-student}"
PI_HOST="${PI_HOST:-192.168.4.1}"
PI_WORKSPACE="${PI_WORKSPACE:-~/ros2_ws}"
LOCAL_WORKSPACE="${LOCAL_WORKSPACE:-$HOME/ros2_ws}"
ROS_DISTRO_NAME="${ROS_DISTRO_NAME:-humble}"
RUN_REMOTE_BUILD="true"
BUILD_SCOPE="romi_base"
SYNC_MODE="src"

usage() {
  cat <<EOF
Usage: $(basename "$0") [--full] [--src-only] [--host HOST] [--user USER] [--remote-workspace PATH] [--local-workspace PATH] [--ros-distro DISTRO] [--no-build] [--all-packages]

Sync ROMI ROS2 sources to a Raspberry Pi and remove stale colcon artifacts on the target first.

Options:
  --full                  Sync the whole workspace except build/install/log.
  --src-only              Sync only src/ROMI-ROS2 (default).
  --host HOST             Override the Pi host. Default: ${PI_HOST}
  --user USER             Override the SSH user. Default: ${PI_USER}
  --remote-workspace PATH Override the remote workspace path. Default: ${PI_WORKSPACE}
  --local-workspace PATH  Override the local workspace path. Default: ${LOCAL_WORKSPACE}
  --ros-distro DISTRO     ROS distro on Pi. Default: ${ROS_DISTRO_NAME}
  --no-build              Skip remote build/validation after sync.
  --all-packages          Build all packages on Pi after sync.
  -h, --help              Show this help.

Environment overrides:
  PI_USER, PI_HOST, PI_WORKSPACE, LOCAL_WORKSPACE, ROS_DISTRO_NAME
EOF
}

while [[ $# -gt 0 ]]; do
  # Parse simple flag/value arguments manually to keep this script dependency-free.
  case "$1" in
    --full)
      SYNC_MODE="full"
      shift
      ;;
    --src-only)
      SYNC_MODE="src"
      shift
      ;;
    --host)
      PI_HOST="$2"
      shift 2
      ;;
    --user)
      PI_USER="$2"
      shift 2
      ;;
    --remote-workspace)
      PI_WORKSPACE="$2"
      shift 2
      ;;
    --local-workspace)
      LOCAL_WORKSPACE="$2"
      shift 2
      ;;
    --ros-distro)
      ROS_DISTRO_NAME="$2"
      shift 2
      ;;
    --no-build)
      RUN_REMOTE_BUILD="false"
      shift
      ;;
    --all-packages)
      BUILD_SCOPE="all"
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

# Fail early with a clear message if required tools are missing.
for required_cmd in ssh rsync; do
  if ! command -v "$required_cmd" >/dev/null 2>&1; then
    echo "Missing required command: $required_cmd" >&2
    exit 127
  fi
done

if [[ ! -d "$LOCAL_WORKSPACE" ]]; then
  echo "Local workspace not found: $LOCAL_WORKSPACE" >&2
  exit 1
fi

# Trim trailing slash to avoid accidental double-slash paths in log output and commands.
REMOTE="${PI_USER}@${PI_HOST}"
REMOTE_WS_CLEAN=${PI_WORKSPACE%/}
LOCAL_WS_CLEAN=${LOCAL_WORKSPACE%/}

# Always wipe generated colcon artifacts on the Pi so cached absolute paths
# from previous machines/runs cannot break the next build.
echo "Removing stale build artifacts on ${REMOTE}:${REMOTE_WS_CLEAN}"
ssh "$REMOTE" "rm -rf ${REMOTE_WS_CLEAN}/build ${REMOTE_WS_CLEAN}/install ${REMOTE_WS_CLEAN}/log && mkdir -p ${REMOTE_WS_CLEAN}/src"

if [[ "$SYNC_MODE" == "full" ]]; then
  # Full mode mirrors the workspace while intentionally skipping generated dirs.
  echo "Syncing full workspace to ${REMOTE}:${REMOTE_WS_CLEAN}"
  rsync -avz --delete \
    --exclude='build/' \
    --exclude='install/' \
    --exclude='log/' \
    --exclude='.vscode/' \
    --exclude='.devcontainer/' \
    --exclude='.docker/' \
    --exclude='.git/' \
    "${LOCAL_WS_CLEAN}/" "$REMOTE:${REMOTE_WS_CLEAN}/"
else
  # Default mode syncs only source code to minimize transfer time and risk.
  echo "Syncing src/ROMI-ROS2 to ${REMOTE}:${REMOTE_WS_CLEAN}/src/ROMI-ROS2"
  rsync -avz --delete \
    --exclude='.vscode/' \
    --exclude='.devcontainer/' \
    --exclude='.docker/' \
    --exclude='.git/' \
    "${LOCAL_WS_CLEAN}/src/ROMI-ROS2/" "$REMOTE:${REMOTE_WS_CLEAN}/src/ROMI-ROS2/"
fi

if [[ "$RUN_REMOTE_BUILD" == "true" ]]; then
  # Build remotely right after sync to catch packaging/environment problems
  # before students try to launch nodes.
  echo "Running remote build + metadata validation on Pi (${ROS_DISTRO_NAME})"
  ssh "$REMOTE" \
    ROS_DISTRO_NAME="$ROS_DISTRO_NAME" \
    REMOTE_WS_CLEAN="$REMOTE_WS_CLEAN" \
    BUILD_SCOPE="$BUILD_SCOPE" \
    'bash -s' <<'EOF'
set -euo pipefail

cd "$REMOTE_WS_CLEAN"

# ROS setup scripts can reference optional vars that are unset under nounset.
# Temporarily disable nounset while sourcing them.
set +u
source "/opt/ros/${ROS_DISTRO_NAME}/setup.bash"

# Build only romi_base by default for a faster, deterministic validation pass.
if [[ "$BUILD_SCOPE" == "all" ]]; then
  colcon build --symlink-install
else
  colcon build --symlink-install --packages-select romi_base
fi

# Validate that Python package metadata exists so ros2 launch entry points resolve.
source install/setup.bash
set -u
python3 -c "import importlib.metadata as m; m.distribution('romi-base'); print('romi-base metadata OK')"

EOF

  echo "Remote build complete and romi-base metadata is present."
  echo "You can now launch on Pi with:"
  echo "  ros2 launch romi_base romi_core.launch.py"
else
  echo "Sync complete. Build on the Pi with:"
  echo "  cd ${REMOTE_WS_CLEAN} && source /opt/ros/${ROS_DISTRO_NAME}/setup.bash && colcon build --symlink-install --packages-select romi_base"
fi
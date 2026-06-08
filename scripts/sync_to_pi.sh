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
REMOTE_CLEAN="false"
FORCE_RPLIDAR_REBUILD="false"

usage() {
  cat <<EOF
Usage: $(basename "$0") [--full] [--src-only] [--host HOST] [--user USER] [--remote-workspace PATH] [--local-workspace PATH] [--ros-distro DISTRO] [--no-build] [--all-packages] [--clean] [--rebuild-rplidar]

Sync ROMI ROS2 sources to a Raspberry Pi.

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
  --clean                 Remove remote build/install/log before syncing.
  --rebuild-rplidar       Force clean rebuild of rplidar_ros on Pi.
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
    --clean)
      REMOTE_CLEAN="true"
      shift
      ;;
    --rebuild-rplidar)
      FORCE_RPLIDAR_REBUILD="true"
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

if [[ "$REMOTE_CLEAN" == "true" ]]; then
  # Use an explicit clean only when the remote workspace needs a hard reset.
  echo "Removing build artifacts on ${REMOTE}:${REMOTE_WS_CLEAN}"
  ssh "$REMOTE" "rm -rf ${REMOTE_WS_CLEAN}/build ${REMOTE_WS_CLEAN}/install ${REMOTE_WS_CLEAN}/log && mkdir -p ${REMOTE_WS_CLEAN}/src"
else
  echo "Preserving remote build/install/log on ${REMOTE}:${REMOTE_WS_CLEAN}"
  ssh "$REMOTE" "mkdir -p ${REMOTE_WS_CLEAN}/src"
fi

if [[ "$SYNC_MODE" == "full" ]]; then
  # Full mode mirrors the workspace while intentionally skipping generated dirs.
  echo "Syncing full workspace to ${REMOTE}:${REMOTE_WS_CLEAN}"
  rsync -avz --no-times --delete \
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
  rsync -avz --no-times --delete \
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
    FORCE_RPLIDAR_REBUILD="$FORCE_RPLIDAR_REBUILD" \
    'bash -s' <<'EOF'
set -euo pipefail

cd "$REMOTE_WS_CLEAN"

# Offline Pi setups often drift in wall-clock time. Normalize file mtimes in
# the active source tree before configuring/building to avoid clock skew errors.
if [[ -d src ]]; then
  find src -type f -exec touch {} +
fi

# ROS setup scripts can reference optional vars that are unset under nounset.
# Temporarily disable nounset while sourcing them.
set +u
source "/opt/ros/${ROS_DISTRO_NAME}/setup.bash"

ROMI_BUILD_STATUS="not-run"
RPLIDAR_BUILD_STATUS="not-run"
ALL_BUILD_STATUS="not-run"

print_build_summary() {
  echo "Build summary:"
  echo "  all packages: ${ALL_BUILD_STATUS}"
  echo "  romi_base: ${ROMI_BUILD_STATUS}"
  echo "  rplidar_ros: ${RPLIDAR_BUILD_STATUS}"
}

run_colcon_build() {
  local label="$1"
  shift

  local build_log
  build_log=$(mktemp)

  echo "Building ${label}..."
  set +e
  colcon build --symlink-install "$@" 2>&1 | tee "$build_log"
  local build_rc=${PIPESTATUS[0]}
  set -e

  LAST_BUILD_LOG="$build_log"
  return "$build_rc"
}

clean_rplidar_pkg() {
  rm -rf build/rplidar_ros install/rplidar_ros
}

build_rplidar_pkg() {
  if run_colcon_build "rplidar_ros" --packages-select rplidar_ros --cmake-clean-cache; then
    RPLIDAR_BUILD_STATUS="success"
    rm -f "$LAST_BUILD_LOG"
    return 0
  fi

  local build_log="$LAST_BUILD_LOG"
  local build_rc=1

  if grep -E -q "undefined reference to .*main|Clock skew detected" "$build_log"; then
    echo "Detected stale or skewed rplidar_ros build artifacts; retrying with a clean package rebuild..."
    clean_rplidar_pkg
    if run_colcon_build "rplidar_ros (retry)" --packages-select rplidar_ros --cmake-clean-cache; then
      RPLIDAR_BUILD_STATUS="success (after retry)"
      rm -f "$build_log" "$LAST_BUILD_LOG"
      return 0
    fi

    build_rc=1
    rm -f "$build_log" "$LAST_BUILD_LOG"
    RPLIDAR_BUILD_STATUS="failed"
    return "$build_rc"
    rm -f "$build_log"
    return 0
  rm -f "$build_log"
  RPLIDAR_BUILD_STATUS="failed"
  build_rc=1
  return "$build_rc"
}

ensure_workspace_setup() {
  if [[ -f install/setup.bash ]]; then
    return 0
  fi

  echo "install/setup.bash is missing; running recovery build for romi_base..."
  if ! run_colcon_build "romi_base (recovery)" --packages-select romi_base; then
    rm -f "$LAST_BUILD_LOG"
    ROMI_BUILD_STATUS="failed"
    return 1
  fi

  rm -f "$LAST_BUILD_LOG"

  if [[ ! -f install/setup.bash ]]; then
    echo "install/setup.bash is still missing after recovery build."
    ROMI_BUILD_STATUS="failed"
    return 1
  fi

  ROMI_BUILD_STATUS="success (recovery)"
  return 0
}

  fi

  rm -f "$build_log"
  return "$build_rc"
  if run_colcon_build "all packages"; then
    ALL_BUILD_STATUS="success"
    rm -f "$LAST_BUILD_LOG"
  else
    ALL_BUILD_STATUS="failed"
    rm -f "$LAST_BUILD_LOG"
    print_build_summary
    exit 1
  fi

  if run_colcon_build "romi_base" --packages-select romi_base; then
    ROMI_BUILD_STATUS="success"
    rm -f "$LAST_BUILD_LOG"
  else
    ROMI_BUILD_STATUS="failed"
    rm -f "$LAST_BUILD_LOG"
    print_build_summary
    exit 1
  fi
# If rplidar_ros has not been built yet, build it once as well so lidar launch
# paths work out-of-the-box on the Pi.
if [[ "$BUILD_SCOPE" == "all" ]]; then
  colcon build --symlink-install
    if ! build_rplidar_pkg; then
      print_build_summary
      exit 1
    fi
  colcon build --symlink-install --packages-select romi_base

  if [[ "$FORCE_RPLIDAR_REBUILD" == "true" ]]; then
    if ! build_rplidar_pkg; then
      print_build_summary
      exit 1
    fi
    clean_rplidar_pkg
    build_rplidar_pkg
    RPLIDAR_BUILD_STATUS="skipped (already present)"
  elif [[ ! -d install/rplidar_ros ]]; then
    echo "rplidar_ros not found in install/. Building rplidar_ros once..."

if ! ensure_workspace_setup; then
  print_build_summary
  exit 1
fi

print_build_summary
    clean_rplidar_pkg
    build_rplidar_pkg
  else
    echo "rplidar_ros already present in install/. Skipping rebuild."
  fi
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
  echo "  cd ${REMOTE_WS_CLEAN} && source /opt/ros/${ROS_DISTRO_NAME}/setup.bash && colcon build --symlink-install --packages-select romi_base rplidar_ros"
fi
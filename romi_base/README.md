# ROMI Unified Bringup

This package now provides a consolidated runtime path for the Pololu ROMI robot:

- `astar_bridge`: hardware bridge to the AStar motor controller
- `base_controller`: combined kinematics + PI wheel control + odometry + TF
- `keyboard_teleop`: keyboard command source (`/cmd_vel`)
- `obstacle_avoidance`: reactive obstacle avoidance using `/scan` from RPLidar

## Launch

Base robot stack only:

```bash
ros2 launch romi_base romi_core.launch.py
```

Full bringup with optional command source and RPLidar A1:

```bash
ros2 launch romi_base romi_robot.launch.py mode:=keyboard_teleop use_lidar:=true
```

Note: `use_lidar:=true` requires the `rplidar_ros` package to be built and sourced.

Autonomous obstacle-avoidance mode:

```bash
ros2 launch romi_base romi_robot.launch.py mode:=obstacle_avoidance use_lidar:=true
```

Robot description only (URDF/Xacro + STL meshes):

```bash
ros2 launch romi_base romi_description.launch.py
```

Robot visualization (description + RViz):

```bash
ros2 launch romi_base romi_rviz.launch.py
```

## Raspberry Pi Build Notes

If you copy this workspace from another machine, do not reuse `build/`, `install/`, or `log/` on the Pi. Colcon and CMake cache absolute paths, so a build generated under `/root/ros2_ws` will fail when reused under `/home/student/ros2_ws`.

Clean the Pi workspace before rebuilding:

```bash
cd ~/ros2_ws
rm -rf build install log
source /opt/ros/<rosdistro>/setup.bash
colcon build --symlink-install
source install/setup.bash
```

If you sync with `rsync`, note that excluded directories are not deleted on the target. This command leaves any old `build/`, `install/`, and `log/` trees in place on the Pi:

```bash
rsync -avz --delete --exclude='*/build/' --exclude='*/install/' --exclude='*/log/' ~/ros2_ws/ student@<pi-host>:~/ros2_ws/
```

Use one of these approaches instead:

```bash
ssh student@<pi-host> 'rm -rf ~/ros2_ws/build ~/ros2_ws/install ~/ros2_ws/log'
rsync -avz --delete ~/ros2_ws/src/ROMI-ROS2/ student@<pi-host>:~/ros2_ws/src/ROMI-ROS2/
```

Or, if you prefer syncing the whole workspace:

```bash
ssh student@<pi-host> 'rm -rf ~/ros2_ws/build ~/ros2_ws/install ~/ros2_ws/log'
rsync -avz --delete --exclude='build/' --exclude='install/' --exclude='log/' ~/ros2_ws/ student@<pi-host>:~/ros2_ws/
```

If `rsync` exits with code `127`, install `rsync` on the machine that reported the error before retrying.

This repository also includes a helper script for the safe sync flow:

```bash
cd ~/ros2_ws/src/ROMI-ROS2
./scripts/sync_to_pi.sh
```

By default it:

- syncs only `src/ROMI-ROS2` to `student@192.168.4.1:~/ros2_ws`
- deletes stale `build/`, `install/`, and `log/` on the Pi
- rebuilds `romi_base` on the Pi and validates Python package metadata (`romi-base`)

Use `--full` to sync the whole workspace, `--all-packages` to build all packages, `--ros-distro <name>` to set the Pi ROS distro, or `--no-build` to sync only.

## Main arguments

- `mode`: `none`, `keyboard_teleop`, or `obstacle_avoidance`
- `use_lidar`: `true` or `false`
- `lidar_serial_port`: default `/dev/ttyUSB0`
- `lidar_frame_id`: default `laser`
- `params_file`: defaults to `config/romi_params.yaml`
- `use_description`: launch robot_state_publisher description stack
- `use_rviz`: launch RViz visualization stack
- `use_simulation`: pass xacro simulation toggle to the description
- `use_joint_state_publisher`: run joint_state_publisher for visualized joints

## Description Assets

- URDF/Xacro files: `description/urdf`
- Mesh files (STL): `description/meshes`
- Source/attribution notes: `description/SOURCE.md`

## Parameters

`config/romi_params.yaml` contains:

- ROMI geometry and control gains (`base_controller_node`)
- encoder polling rate (`astar_bridge_node`)
- obstacle behavior thresholds (`obstacle_avoidance_node`)

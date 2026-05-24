# ROMI Unified Bringup

This package provides a beginner-friendly runtime stack for a Pololu ROMI robot using ROS 2.

- `astar_bridge`: hardware bridge to the AStar motor controller
- `base_controller`: combined kinematics + PI wheel control + odometry + TF
- `teleop_twist_keyboard`: keyboard command source (`/cmd_vel`)
- `obstacle_avoidance`: reactive obstacle avoidance using `/scan` from RPLidar

## System Overview

- Raspberry Pi 4 runs the ROS 2 robot software.
- ROMI 32U4 board handles low-level motor and encoder I/O.
- A laptop is used for development, launch, teleop, and visualization.

## Prerequisites

- Hardware:
  - Pololu ROMI with Romi 32U4 control board
  - Raspberry Pi 4 (recommended)
  - microSD card (32 GB or larger recommended)
  - USB cable for flashing the 32U4 board
- Software:
  - ROS 2 (Humble or compatible distro)
  - `colcon` build tools
  - `git`, `ssh`, and `rsync`
  - Optional: Gazebo Sim (`ros_gz`) and RViz for simulation/visualization

## 1) Configure Robot Hardware

### Flash ROMI 32U4 firmware

If your ROMI control board is not already flashed:

1. Install Arduino IDE.
2. Add Pololu board manager URL in Arduino IDE:
   `https://files.pololu.com/arduino/package_pololu_index.json`
3. Install `Pololu A-Star Boards` and `Romi32U4` library.
4. Open and upload:
   `lab_assets/arduino/RomiRPiSlaveDemo/RomiRPiSlaveDemo.ino`

### Prepare Raspberry Pi

1. Flash a ROS 2-ready image onto the Pi microSD card.
2. Boot the Pi and connect it to your network.
3. Verify SSH access from your laptop:

```bash
ssh <user>@<pi-host>
```

## 2) Create Workspace and Clone Repository

```bash
mkdir -p ~/ros2_ws/src
cd ~/ros2_ws/src
git clone https://github.com/UNCC-Embedded-Lab/ROMI-ROS2
```

## 3) Build the Workspace

From the workspace root:

```bash
cd ~/ros2_ws
source /opt/ros/<rosdistro>/setup.bash
colcon build --symlink-install
source install/setup.bash
```

To build just this package:

```bash
cd ~/ros2_ws
source /opt/ros/<rosdistro>/setup.bash
colcon build --symlink-install --packages-select romi_base
source install/setup.bash
```

## 4) Sync Workspace to Raspberry Pi

Do not reuse `build/`, `install/`, or `log/` across different machines.
Those directories contain absolute paths and should be regenerated locally.

Recommended sync flow:

```bash
cd ~/ros2_ws/src/ROMI-ROS2
./scripts/sync_to_pi.sh
```

Manual sync example:

```bash
ssh <user>@<pi-host> 'rm -rf ~/ros2_ws/build ~/ros2_ws/install ~/ros2_ws/log'
rsync -avz --delete ~/ros2_ws/src/ROMI-ROS2/ <user>@<pi-host>:~/ros2_ws/src/ROMI-ROS2/
```

Then rebuild on the Pi:

```bash
ssh <user>@<pi-host>
cd ~/ros2_ws
source /opt/ros/<rosdistro>/setup.bash
colcon build --symlink-install --packages-select romi_base
source install/setup.bash
```

## 5) Launch Examples

If launching on a physical Pi and you want robot description or RViz on the Pi itself, install:

```bash
sudo apt-get update
sudo apt-get install -y ros-humble-xacro ros-humble-teleop-twist-keyboard
```

If the Pi is offline, hardware control can still run without `xacro` by skipping description/RViz:

```bash
ros2 launch romi_base romi_core.launch.py use_description:=false use_rviz:=false
```

Base robot stack only:

```bash
ros2 launch romi_base romi_core.launch.py
```

Robot bringup with keyboard teleop (`teleop_twist_keyboard`) and lidar:

```bash
ros2 launch romi_base romi_robot.launch.py mode:=teleop_twist_keyboard use_lidar:=true
```

Obstacle avoidance mode:

```bash
ros2 launch romi_base romi_robot.launch.py mode:=obstacle_avoidance use_lidar:=true
```

Description only (URDF/Xacro):

```bash
ros2 launch romi_base romi_description.launch.py
```

Description + RViz:

```bash
ros2 launch romi_base romi_rviz.launch.py
```

Gazebo Sim (modern `ros_gz`) through unified bringup:

```bash
ros2 launch romi_base romi_robot.launch.py use_gazebo:=true mode:=teleop_twist_keyboard use_rviz:=true
```

Note: `mode:=teleop_twist_keyboard` launches the generic ROS node from the `teleop_twist_keyboard` package.

Direct Gazebo Sim launch:

```bash
ros2 launch romi_base romi_gz.launch.py mode:=teleop_twist_keyboard use_rviz:=true
```

Modern Gazebo defaults to: `worlds/romi_simple_gz.sdf`.
To override it:

```bash
ros2 launch romi_base romi_robot.launch.py \
  use_gazebo:=true \
  mode:=teleop_twist_keyboard \
  gazebo_world:=/root/ros2_ws/src/ROMI-ROS2/romi_base/worlds/romi_simple_gz.sdf
```

Note: `use_lidar:=true` requires `rplidar_ros` to be built and sourced.

Note: This package now uses modern Gazebo Sim launch files only. The legacy Classic launch entry (`romi_gazebo.launch.py`) is intentionally removed.

## Main Launch Arguments

- `mode`: `none`, `teleop_twist_keyboard`, or `obstacle_avoidance`
- `use_lidar`: `true` or `false`
- `lidar_serial_port`: default `/dev/ttyUSB0`
- `lidar_frame_id`: default `laser`
- `params_file`: defaults to `config/romi_params.yaml`
- `use_gazebo`: run Gazebo simulation instead of hardware stack
- `gazebo_world`: world file path used when `use_gazebo:=true`
- `use_description`: launch robot_state_publisher description stack
- `use_rviz`: launch RViz visualization stack
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

# ROMI Unified Bringup

This package provides a beginner-friendly runtime stack for a Pololu ROMI robot using ROS 2.

- `astar_bridge`: hardware bridge to the AStar motor controller; also reads the onboard
  LSM6DS33 accelerometer/gyro directly over I2C and publishes it to `/imu/data_raw`
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
   Do **not** install the `LSM6` library or add `#include <Wire.h>`/`#include <LSM6.h>`
   to the sketch: `PololuRPiSlave`'s TWI slave interrupt and the standard `Wire`
   library's TWI master interrupt both need the AVR's single TWI interrupt vector,
   so linking both into the sketch fails with "multiple definition of `__vector_36`".
   The onboard LSM6DS33 accelerometer/gyro is instead read directly by the Raspberry
   Pi over the same I2C bus (see `astar_bridge_node`/`lsm6_interface.py`), not through
   the firmware.
4. Open and upload:
   `lab_assets/arduino/RomiRPiSlaveDemo/RomiRPiSlaveDemo.ino`

### Prepare Raspberry Pi

1. Flash a ROS 2-ready image onto the Pi microSD card. The provided Pi image can be
   downloaded here:
   [romiPi20260723.img.xz](https://github.com/UNCC-Embedded-Lab/ROMI-ROS2/releases/download/pi-image/romiPi20260723.img.xz)
2. Boot the Pi and connect it to your network.
3. Verify SSH access from your laptop:

Default credentials for the provided Pi image are:

- User: `student`
- Host: `192.168.4.1`
- Password: `romi32u4`

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

### On the Raspberry Pi

Minimal hardware stack (no lidar):

```bash
ros2 launch romi_base romi_core.launch.py
```

Full hardware stack with lidar:

```bash
ros2 launch romi_base romi_robot.launch.py
```

Without lidar:

```bash
ros2 launch romi_base romi_robot.launch.py use_lidar:=false
```

### On the Laptop

Open RViz pre-configured for ROMI topics:

```bash
ros2 launch romi_base romi_rviz.launch.py
```

Keyboard teleop (separate terminal):

```bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

Obstacle avoidance node (separate terminal):

```bash
ros2 run romi_base obstacle_avoidance
```

### Simulation (laptop, requires X11 or Wayland display)

The default simulation world is an office-building interior (`romi_office_gz.sdf`) that contains
walls, a hallway, and four rooms — suitable for testing AMCL localisation.

```bash
ros2 launch romi_base romi_gz.launch.py
```

Without Gazebo GUI (headless):

```bash
ros2 launch romi_base romi_gz.launch.py use_gazebo_gui:=false
```

Override world file (e.g. to go back to the simple open world):

```bash
ros2 launch romi_base romi_gz.launch.py \
  world:=$(ros2 pkg prefix romi_base)/share/romi_base/worlds/romi_simple_gz.sdf
```

### AMCL Localisation (simulation)

AMCL requires `nav2_map_server`, `nav2_amcl`, and `nav2_lifecycle_manager`:

```bash
sudo apt install ros-humble-nav2-map-server ros-humble-nav2-amcl ros-humble-nav2-lifecycle-manager
```

Run the simulation and localisation stacks in separate terminals:

```bash
# Terminal 1 — Gazebo simulation
ros2 launch romi_base romi_gz.launch.py

# Terminal 2 — AMCL localisation
ros2 launch romi_base romi_amcl_sim.launch.py
```

The robot spawns at the world origin (centre of the hallway). `set_initial_pose: true` in
`config/amcl_params.yaml` initialises the particle cloud there automatically — no manual
"2D Pose Estimate" click in RViz is needed.

To visualise localisation, open RViz and add:
- **Map** → topic `/map`
- **LaserScan** → topic `/scan`
- **PoseArray** → topic `/particle_cloud` (AMCL particles)

Verify the full TF tree with:

```bash
ros2 run tf2_tools view_frames
```

Expected chain: `map → odom → base_link → chassis → lidar_frame`

Note: `romi_robot.launch.py` requires `rplidar_ros` to be built and sourced when `use_lidar:=true` (the default).

Note: Launch files do not start `teleop_twist_keyboard` automatically. Keep teleop in a separate interactive terminal.

## Launch Files

| File | Runs on | Purpose |
|---|---|---|
| `romi_core.launch.py` | Pi | Minimal hardware stack: `astar_bridge`, `base_controller`, `robot_state_publisher`, `joint_state_publisher` |
| `romi_robot.launch.py` | Pi | Full hardware stack: same as `romi_core` plus optional RPLidar |
| `romi_gz.launch.py` | Laptop | Gazebo Sim with full robot simulation (default world: office interior) |
| `romi_amcl_sim.launch.py` | Laptop | AMCL localisation (simulation only): `map_server` + `amcl` + `lifecycle_manager` |
| `romi_rviz.launch.py` | Laptop | RViz only, pre-configured for ROMI topics |

## Launch Arguments

### `romi_core.launch.py`

- `params_file`: defaults to `config/romi_params.yaml`

### `romi_robot.launch.py`

- `params_file`: defaults to `config/romi_params.yaml`
- `use_lidar`: `true` or `false` (default `true`)
- `lidar_serial_port`: default `/dev/ttyUSB0`
- `lidar_frame_id`: default `lidar_frame`

### `romi_gz.launch.py`

- `world`: path to Gazebo world SDF file
- `use_gazebo_gui`: `true` or `false` (default `true`)
- `use_rviz`: `true` or `false` (default `false`)
- `rviz_config`: path to RViz config file

### `romi_amcl_sim.launch.py`

- `map`: full path to a map YAML file (default: `maps/romi_office_map.yaml`)
- `params_file`: full path to the params YAML file (default: `config/amcl_params.yaml`)

### `romi_rviz.launch.py`

- `use_sim_time`: `true` or `false` (default `false`)
- `rviz_config`: path to RViz config file

## Description Assets

- URDF/Xacro files: `description/urdf`
- Mesh files (STL): `description/meshes`
- Source/attribution notes: `description/SOURCE.md`

## Simulation Worlds

| File | Description |
|---|---|
| `worlds/romi_office_gz.sdf` | Office interior: sealed 6 m × 6 m room with a central hallway, four rooms, and furniture. Default world for `romi_gz.launch.py`. Designed for AMCL testing. |
| `worlds/romi_simple_gz.sdf` | Open flat ground with a few box obstacles. Useful for basic motion testing. |

## Maps

Pre-built 2D occupancy-grid maps for use with AMCL (`nav2_map_server`).

| File | Description |
|---|---|
| `maps/romi_office_map.pgm` | Binary occupancy grid image matching `romi_office_gz.sdf` (160 × 160 px, 0.05 m/px) |
| `maps/romi_office_map.yaml` | Map metadata: resolution, origin, threshold values |

## Parameters

`config/romi_params.yaml` contains:

- ROMI geometry and control gains (`base_controller_node`)
- encoder and IMU polling rates, and IMU frame ID (`astar_bridge_node`)
- obstacle behavior thresholds (`obstacle_avoidance_node`)

`config/amcl_params.yaml` contains:

- AMCL particle filter settings (particles, update thresholds, motion model noise)
- Likelihood-field laser model settings tuned for the RPLidar A1
- Initial pose at the world origin (hallway centre)
- `map_server` and `lifecycle_manager` parameters

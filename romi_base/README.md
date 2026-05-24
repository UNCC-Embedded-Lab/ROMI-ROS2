# ROMI Unified Bringup

This package now provides a consolidated runtime path for the Pololu ROMI robot:

- `astar_bridge`: hardware bridge to the AStar motor controller
- `base_controller`: combined kinematics + PI wheel control + odometry + TF
- `keyboard_teleop`: keyboard command source (`/cmd_vel`)
- `obstacle_avoidance`: reactive obstacle avoidance using `/scan` from RPLidar

## Course Lab Integration

This repository is intended to be used with two additional course assets:

- Raspberry Pi class image files in `lab_assets/pi_image`
- Romi32U4 Arduino firmware in `lab_assets/arduino`

### System architecture

- Raspberry Pi 4B is the high-level compute node (ROS 2 bringup, sensing, planning).
- Romi 32U4 control board is the low-level controller (PWM and encoder handling).
- Student laptop is the operator console (development, launch, teleop, visualization).

This separates high-level decision making from real-time motor/encoder execution and is the expected architecture for the lab exercises.

### ROS 2 basics used in this course

- Nodes are single-purpose programs.
- Topics are communication channels.
- Publishers write messages to topics.
- Subscribers read messages from topics.

In early labs, laptop-side nodes publish commands while Pi-side nodes subscribe and convert commands into hardware actions.

## Lab 1 Setup Guide

### Required materials

- Romi 32U4 control board
- Micro USB cable
- Laptop (Windows preferred for this workflow)
- Raspberry Pi 4B
- 32 GB or larger microSD card

### Step 1: Arduino IDE and Romi firmware

Step 1 is only needed for students using personal Romi kits. Lab-provided robots may already be flashed.

1. Install Arduino IDE for your OS.
2. On Windows, install Pololu A-Star Windows drivers (`a-star.inf`).
3. In Arduino IDE, add Pololu board manager URL:
	`https://files.pololu.com/arduino/package_pololu_index.json`
4. Install `Pololu A-Star Boards` from Boards Manager.
5. Install the `Romi32U4` library from Library Manager.
6. Open the course sketch at:
	`lab_assets/arduino/RomiRPiSlaveDemo/RomiRPiSlaveDemo.ino`
7. Upload it to the Romi 32U4 control board.

### Step 2: Raspberry Pi image

1. Download the class Pi image.
2. Install Raspberry Pi Imager.
3. Insert microSD card.
4. In Pi Imager:
	- Device: Raspberry Pi 4
	- OS: Use Custom (select class image)
	- Storage: your microSD card
5. Flash image and insert card into the Pi.

### Step 3: ROS 2 on Windows (WSL2)

1. In elevated PowerShell:
	- `wsl --install`
	- `wsl --install -d Ubuntu-22.04`
2. In WSL Ubuntu:
	- install ROS 2 desktop + dev tools (course distro)
	- add ROS setup to shell startup:
	  `echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc`
3. For ROS 2 networking in WSL:
	- set WSL networking mode to Mirrored
	- allow inbound Hyper-V VM firewall traffic:
	  `Set-NetFirewallHyperVVMSetting -Name '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}' -DefaultInboundAction Allow`

### Step 4: Clone course repository

In WSL:

```bash
cd ~
mkdir -p ros2_ws/src
cd ros2_ws/src
git clone https://github.com/UNCC-Embedded-Lab/ROMI-ROS2
```

### Step 5: VS Code setup

1. Install VS Code.
2. Ensure installer option `Add to PATH` is selected.
3. Install the `WSL` extension.
4. Use `WSL: Connect to WSL using Distro...` and open your WSL home/workspace folder.

### Step 6: Hardware bringup and SSH

1. Mount Pi on Romi header in correct orientation.
2. For LED-only validation, USB power is sufficient.
3. Wait for first boot and AP creation (`Romi-XXXX`).
4. Connect laptop to `Romi-XXXX` Wi-Fi (password: `roboticsisfun`).
5. SSH into the robot:

```bash
ssh student@192.168.4.1
```

Default password: `ecgr4161`

### Step 7: End-to-end validation target

For initial communication validation:

- Run the Pi-side subscriber/hardware interface node.
- Run the laptop-side publisher node.
- Confirm physical LED behavior matches published commands.

This validates cross-device ROS 2 communication before moving to full mobility labs.

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

# Docker Launch Guide (ROS 2 + ROMI)

This guide shows how to start a Docker container for this workspace, build packages, and run ROMI nodes.

## Prerequisites

- Docker Engine installed and running
- Linux host (or WSL2 with Docker Desktop integration)
- Workspace path on host: `~/ros2_ws`
- X11 display server available on host if using Gazebo GUI

## 1) Pull a ROS 2 image

Use a ROS 2 desktop image (includes common GUI tools):

```bash
docker pull osrf/ros:humble-desktop
```

## 2) Share the workspace directory

Use a bind mount (`-v`) so the container can read and write your host files.

Important: `-v ...` is not a standalone shell command. It must be part of `docker run`.

Share full workspace (recommended):

```bash
-v ~/ros2_ws:/root/ros2_ws
```

Share only this repository:

```bash
-v ~/ros2_ws/src/ROMI-ROS2:/root/ros2_ws/src/ROMI-ROS2
```

To avoid path mistakes, you can use `${PWD}` while in the repo root:

```bash
cd ~/ros2_ws/src/ROMI-ROS2
-v ${PWD}:/root/ros2_ws/src/ROMI-ROS2
```

Working one-line example:

```bash
docker run -it --name romi_ros2 --net=host -e ROS_DOMAIN_ID=0 -e ROS_LOCALHOST_ONLY=0 -v ~/ros2_ws:/root/ros2_ws -w /root/ros2_ws osrf/ros:humble-desktop
```

## 3) Start a container (simulation-friendly)

This starts a reusable container named `romi_ros2` and mounts your workspace.
Do not add `--rm` if you want to keep installed packages between sessions.

```bash
docker run -it --name romi_ros2 \
  --net=host \
  -e DISPLAY=$DISPLAY \
  -e ROS_DOMAIN_ID=0 \
  -e ROS_LOCALHOST_ONLY=0 \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v ~/ros2_ws:/root/ros2_ws \
  -w /root/ros2_ws \
  osrf/ros:humble-desktop
```

Before starting the container, allow local root user access to your X server:

```bash
xhost +local:root
```

Optional hardening after you finish:

```bash
xhost -local:root
```

Inside the container, run:

```bash
source /opt/ros/humble/setup.bash
apt-get update
apt-get install -y ros-humble-ros-gz ros-humble-xacro ros-humble-teleop-twist-keyboard
colcon build --symlink-install
source install/setup.bash
```

The install command above is usually needed only once per container.
On later sessions, just restart and re-enter the same container.

## 4) Launch ROMI nodes from the container

Recommended Gazebo flow (prevents keyboard teleop TTY error):

Terminal 1 inside container (Gazebo + robot):

```bash
source /opt/ros/humble/setup.bash
source /root/ros2_ws/install/setup.bash
ros2 launch romi_base romi_robot.launch.py use_gazebo:=true mode:=none use_rviz:=true
```

Terminal 2 inside container (interactive keyboard teleop):

```bash
docker exec -it romi_ros2 bash
source /opt/ros/humble/setup.bash
source /root/ros2_ws/install/setup.bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

If Gazebo GUI is not required, you can run headless server only:

```bash
source /opt/ros/humble/setup.bash
source /root/ros2_ws/install/setup.bash
ros2 launch romi_base romi_gz.launch.py mode:=none
```

Core stack:

```bash
source /opt/ros/humble/setup.bash
source /root/ros2_ws/install/setup.bash
ros2 launch romi_base romi_core.launch.py
```

Gazebo simulation:

```bash
source /opt/ros/humble/setup.bash
source /root/ros2_ws/install/setup.bash
ros2 launch romi_base romi_robot.launch.py use_gazebo:=true mode:=none use_rviz:=true
```

Full robot launch (hardware path + generic keyboard teleop mode):

```bash
source /opt/ros/humble/setup.bash
source /root/ros2_ws/install/setup.bash
ros2 launch romi_base romi_robot.launch.py mode:=teleop_twist_keyboard use_lidar:=true
```

## 5) Start a hardware-access container (USB/I2C)

If you need direct hardware access (serial lidar, i2c, etc.), start with devices mapped:

```bash
docker run -it --name romi_ros2_hw \
  --net=host \
  --privileged \
  -e ROS_DOMAIN_ID=0 \
  -e ROS_LOCALHOST_ONLY=0 \
  -v ~/ros2_ws:/root/ros2_ws \
  -v /dev:/dev \
  -w /root/ros2_ws \
  osrf/ros:humble-desktop
```

If you prefer narrower permissions, replace `--privileged` with specific device flags, for example:

```bash
--device /dev/ttyUSB0 --device /dev/i2c-1
```

## 6) Re-enter, stop, and remove container

Re-enter an existing container:

```bash
docker start romi_ros2
docker exec -it romi_ros2 bash
```

Recommended daily workflow (reuse container state):

```bash
docker start romi_ros2
docker exec -it romi_ros2 bash
```

Stop container:

```bash
docker stop romi_ros2
```

Remove container:

```bash
docker rm romi_ros2
```

## 7) Common issues

- `colcon: command not found`
  - Run `source /opt/ros/humble/setup.bash` first.
- Package not found at launch
  - Install missing ROS dependencies once in the container, then rebuild and source:
    `apt-get update && apt-get install -y ros-humble-ros-gz ros-humble-xacro ros-humble-teleop-twist-keyboard`
    `colcon build --symlink-install && source install/setup.bash`
- ROS nodes cannot discover each other
  - Verify all machines/containers use same `ROS_DOMAIN_ID` and have reachable networking.
- Permission denied on serial devices
  - Run with `--privileged` or map the specific device using `--device`.

# Docker Launch Guide (ROS 2 + ROMI)

This guide is a minimal, repeatable flow for:
1. Setting up a ROS 2 Humble container environment.
2. Enabling X11 GUI access.
3. Starting a persistent container with your shared workspace.

## 1) Setup and Installation

Prerequisites:
- Docker Engine running on the host.
- Linux host (or WSL2 + Docker Desktop integration).
- Host workspace at `~/ros2_ws`.

Pull the base image:

```bash
docker pull osrf/ros:humble-desktop
```

Create the container once (persistent environment):

```bash
docker run -it --name romi_ros2 \
  --net=host \
  -e ROS_DOMAIN_ID=0 \
  -e ROS_LOCALHOST_ONLY=0 \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v ~/ros2_ws:/root/ros2_ws \
  -w /root/ros2_ws \
  osrf/ros:humble-desktop
```

Inside the container, install dependencies and build once:

```bash
source /opt/ros/humble/setup.bash
apt-get update
apt-get install -y ros-humble-ros-gz ros-humble-xacro ros-humble-teleop-twist-keyboard
colcon build --symlink-install
source install/setup.bash
```

Optionally make this automatic for every new shell in the container:

```bash
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
echo "source /root/ros2_ws/install/setup.bash" >> ~/.bashrc
source ~/.bashrc
```

## 2) Enable X11 for GUI Features

Run this on the host before launching GUI apps from the container:

```bash
xhost +local:root
```

Optional cleanup after you are done:

```bash
xhost -local:root
```

## 3) Start the Persistent Container with Shared Workspace

For daily use, reuse the same container so installed packages and build artifacts persist:

```bash
docker start romi_ros2
docker exec -it romi_ros2 bash
```

Inside the container each session:

```bash
source /opt/ros/humble/setup.bash
source /root/ros2_ws/install/setup.bash
```

You can now run your launch commands (for example, Gazebo or RViz) from this shell.

## 4) Use the Same Container in VS Code and Terminal

This repository now includes `.devcontainer/devcontainer.json` configured with
`containerName: romi_ros2`.

Recommended flow:

1. Start the container from a host terminal:

```bash
docker start romi_ros2
```

2. In VS Code, run: `Dev Containers: Attach to Running Container...` and choose `romi_ros2`.

3. In any host terminal, open another shell in the same container:

```bash
docker exec -it romi_ros2 bash
```

Both VS Code and terminal sessions will then share the same container state, files, and installed dependencies.

If you prefer VS Code to start the container (instead of attaching to one that is already running), open this repository in VS Code and run `Dev Containers: Reopen in Container`.
With this repository's `.devcontainer/devcontainer.json`, VS Code will create/start `romi_ros2` for you and reuse it on later sessions.

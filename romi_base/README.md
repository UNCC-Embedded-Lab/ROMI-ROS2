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

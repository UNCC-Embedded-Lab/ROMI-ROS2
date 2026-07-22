#!/usr/bin/env python3
"""
romi_amcl_sim.launch.py
-----------------------
Launches nav2 map_server + AMCL localisation for the Romi robot IN SIMULATION.

This launch file is sim-only: the accompanying config/amcl_params.yaml sets
use_sim_time: true and a fixed initial_pose at the world origin, both of which
match the Gazebo world and will NOT work on the real robot as-is.

Run AFTER (or alongside) romi_gz.launch.py:

  # Terminal 1 — simulation
  ros2 launch romi_base romi_gz.launch.py

  # Terminal 2 — localisation
  ros2 launch romi_base romi_amcl_sim.launch.py

The lifecycle_manager will automatically configure and activate both
map_server and amcl, so no manual lifecycle calls are needed.

To visualise localisation in RViz, add these displays:
  - Map            (topic: /map)
  - LaserScan      (topic: /scan)
  - PoseArray      (topic: /particle_cloud)   ← AMCL particles
  - Odometry       (topic: /odom)
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory('romi_base')

    # Default paths — both installed into the package share directory
    default_map  = os.path.join(pkg_share, 'maps',   'romi_office_map.yaml')
    default_params = os.path.join(pkg_share, 'config', 'amcl_params.yaml')

    map_yaml  = LaunchConfiguration('map')
    params_file = LaunchConfiguration('params_file')

    return LaunchDescription([

        # ── Launch arguments ──────────────────────────────────────────────────
        DeclareLaunchArgument(
            'map',
            default_value=default_map,
            description='Full path to the map YAML file to load',
        ),
        DeclareLaunchArgument(
            'params_file',
            default_value=default_params,
            description='Full path to the ROS 2 params file for amcl and map_server',
        ),

        # ── map_server ────────────────────────────────────────────────────────
        # Loads the occupancy grid from disk and publishes it on /map.
        # yaml_filename overrides the placeholder value in amcl_params.yaml.
        Node(
            package='nav2_map_server',
            executable='map_server',
            name='map_server',
            output='screen',
            parameters=[
                params_file,
                {'yaml_filename': map_yaml},
            ],
        ),

        # ── amcl ──────────────────────────────────────────────────────────────
        # Adaptive Monte Carlo Localisation.
        # Subscribes to /scan and /map, publishes map→odom TF correction.
        Node(
            package='nav2_amcl',
            executable='amcl',
            name='amcl',
            output='screen',
            parameters=[params_file],
        ),

        # ── lifecycle_manager ─────────────────────────────────────────────────
        # Drives map_server and amcl through configure → activate automatically.
        # Without this, both nodes remain in 'unconfigured' state and do nothing.
        Node(
            package='nav2_lifecycle_manager',
            executable='lifecycle_manager',
            name='lifecycle_manager_localization',
            output='screen',
            parameters=[params_file],
        ),
    ])

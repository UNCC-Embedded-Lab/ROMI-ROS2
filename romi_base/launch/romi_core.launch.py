#!/usr/bin/env python3

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory('romi_base')
    xacro_file = f'{pkg_share}/description/urdf/romi.urdf.xacro'

    params_file = LaunchConfiguration('params_file')

    robot_description = {
        'robot_description': Command(['xacro ', xacro_file, ' use_simulation:=false'])
    }

    return LaunchDescription([
        DeclareLaunchArgument(
            'params_file',
            default_value=f'{pkg_share}/config/romi_params.yaml',
            description='Path to ROMI parameter file',
        ),
        Node(
            package='romi_base',
            executable='astar_bridge',
            name='astar_bridge_node',
            parameters=[params_file],
            output='screen',
        ),
        Node(
            package='romi_base',
            executable='base_controller',
            name='base_controller_node',
            parameters=[params_file],
            output='screen',
        ),
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            parameters=[robot_description, {'publish_robot_description': True, 'use_sim_time': False}],
            output='screen',
        ),
        Node(
            package='joint_state_publisher',
            executable='joint_state_publisher',
            name='joint_state_publisher',
            parameters=[robot_description, {'use_gui': False, 'use_sim_time': False}],
            output='screen',
        ),
    ])

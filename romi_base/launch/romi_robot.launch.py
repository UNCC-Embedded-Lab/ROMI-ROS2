#!/usr/bin/env python3

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    romi_pkg_share = get_package_share_directory('romi_base')
    xacro_file = f'{romi_pkg_share}/description/urdf/romi.urdf.xacro'

    params_file = LaunchConfiguration('params_file')
    use_lidar = LaunchConfiguration('use_lidar')
    lidar_serial_port = LaunchConfiguration('lidar_serial_port')
    lidar_frame_id = LaunchConfiguration('lidar_frame_id')

    robot_description = {
        'robot_description': Command(['xacro ', xacro_file, ' use_simulation:=false'])
    }

    return LaunchDescription([
        DeclareLaunchArgument(
            'params_file',
            default_value=f'{romi_pkg_share}/config/romi_params.yaml',
            description='Path to ROMI parameter file',
        ),
        DeclareLaunchArgument(
            'use_lidar',
            default_value='true',
            description='Launch RPLidar A1 node',
        ),
        DeclareLaunchArgument(
            'lidar_serial_port',
            default_value='/dev/ttyUSB0',
            description='Serial device path for RPLidar A1',
        ),
        DeclareLaunchArgument(
            'lidar_frame_id',
            default_value='lidar_frame',
            description='Frame id for LaserScan messages',
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
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                PathJoinSubstitution([
                    FindPackageShare('rplidar_ros'),
                    'launch',
                    'rplidar_a1_launch.py',
                ])
            ),
            condition=IfCondition(use_lidar),
            launch_arguments={
                'serial_port': lidar_serial_port,
                'frame_id': lidar_frame_id,
            }.items(),
        ),
    ])

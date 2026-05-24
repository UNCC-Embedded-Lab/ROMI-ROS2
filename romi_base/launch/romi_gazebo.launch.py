#!/usr/bin/env python3

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory('romi_base')
    gazebo_share = get_package_share_directory('gazebo_ros')

    world = LaunchConfiguration('world')
    use_rviz = LaunchConfiguration('use_rviz')
    mode = LaunchConfiguration('mode')
    rviz_config = LaunchConfiguration('rviz_config')

    return LaunchDescription([
        DeclareLaunchArgument(
            'world',
            default_value=f'{gazebo_share}/worlds/empty.world',
            description='Gazebo world file',
        ),
        DeclareLaunchArgument(
            'use_rviz',
            default_value='false',
            description='Launch RViz alongside Gazebo',
        ),
        DeclareLaunchArgument(
            'rviz_config',
            default_value=f'{pkg_share}/rviz/romi_base.rviz',
            description='Path to RViz config file',
        ),
        DeclareLaunchArgument(
            'mode',
            default_value='none',
            description='Robot command source: none | keyboard_teleop | obstacle_avoidance',
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(f'{gazebo_share}/launch/gazebo.launch.py'),
            launch_arguments={'world': world}.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(f'{pkg_share}/launch/romi_description.launch.py'),
            launch_arguments={
                'use_simulation': 'true',
                'use_joint_state_publisher': 'false',
            }.items(),
        ),
        Node(
            package='gazebo_ros',
            executable='spawn_entity.py',
            name='spawn_romi_base',
            arguments=['-entity', 'romi_base', '-topic', 'robot_description'],
            output='screen',
        ),
        Node(
            package='romi_base',
            executable='keyboard_teleop',
            name='keyboard_teleop_node',
            condition=IfCondition(PythonExpression(["'", mode, "' == 'keyboard_teleop'"])),
            output='screen',
        ),
        Node(
            package='romi_base',
            executable='obstacle_avoidance',
            name='obstacle_avoidance_node',
            condition=IfCondition(PythonExpression(["'", mode, "' == 'obstacle_avoidance'"])),
            output='screen',
        ),
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            condition=IfCondition(use_rviz),
            arguments=['-d', rviz_config],
            output='screen',
        ),
    ])

#!/usr/bin/env python3

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory('romi_base')
    use_simulation = LaunchConfiguration('use_simulation')
    use_sim_time = LaunchConfiguration('use_sim_time')

    xacro_file = f'{pkg_share}/description/urdf/romi.urdf.xacro'
    robot_description = {
        'robot_description': Command([
            'xacro ',
            xacro_file,
            ' use_simulation:=',
            use_simulation,
        ])
    }

    return LaunchDescription([
        DeclareLaunchArgument(
            'use_simulation',
            default_value='false',
            description='Enable simulation-specific robot description tags',
        ),
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='false',
            description='Use simulation clock if true',
        ),
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            parameters=[
                robot_description,
                {
                    'publish_robot_description': True,
                    'use_sim_time': use_sim_time,
                },
            ],
            output='screen',
        ),
        Node(
            package='joint_state_publisher',
            executable='joint_state_publisher',
            name='joint_state_publisher',
            parameters=[
                robot_description,
                {
                    'use_gui': False,
                    'use_sim_time': use_sim_time,
                },
            ],
            output='screen',
        ),
    ])

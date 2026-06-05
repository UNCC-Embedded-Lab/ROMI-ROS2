#!/usr/bin/env python3

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory('romi_base')

    use_simulation = LaunchConfiguration('use_simulation')
    use_sim_time = LaunchConfiguration('use_sim_time')
    use_joint_state_publisher = LaunchConfiguration('use_joint_state_publisher')
    rviz_config = LaunchConfiguration('rviz_config')

    return LaunchDescription([
        DeclareLaunchArgument(
            'use_simulation',
            default_value='false',
            description='Enable simulation-specific robot description tags',
        ),
        DeclareLaunchArgument(
            'use_joint_state_publisher',
            default_value='true',
            description='Run joint_state_publisher for model visualization',
        ),
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='false',
            description='Use simulation clock if true',
        ),
        DeclareLaunchArgument(
            'rviz_config',
            default_value=f'{pkg_share}/rviz/romi_base.rviz',
            description='Path to RViz config file',
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(f'{pkg_share}/launch/romi_description.launch.py'),
            launch_arguments={
                'use_simulation': use_simulation,
                'use_joint_state_publisher': use_joint_state_publisher,
                'use_sim_time': use_sim_time,
            }.items(),
        ),
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            arguments=['-d', rviz_config],
            parameters=[{'use_sim_time': use_sim_time}],
            output='screen',
        ),
    ])

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

    params_file = LaunchConfiguration('params_file')
    use_description = LaunchConfiguration('use_description')
    use_rviz = LaunchConfiguration('use_rviz')
    use_simulation = LaunchConfiguration('use_simulation')
    use_joint_state_publisher = LaunchConfiguration('use_joint_state_publisher')

    return LaunchDescription([
        DeclareLaunchArgument(
            'params_file',
            default_value=f'{pkg_share}/config/romi_params.yaml',
            description='Path to ROMI parameter file',
        ),
        DeclareLaunchArgument(
            'use_description',
            default_value='true',
            description='Launch robot_state_publisher and robot description',
        ),
        DeclareLaunchArgument(
            'use_rviz',
            default_value='false',
            description='Launch RViz with ROMI visualization config',
        ),
        DeclareLaunchArgument(
            'use_simulation',
            default_value='false',
            description='Enable simulation-specific tags in xacro',
        ),
        DeclareLaunchArgument(
            'use_joint_state_publisher',
            default_value='true',
            description='Run joint_state_publisher for model visualization',
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
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(f'{pkg_share}/launch/romi_description.launch.py'),
            condition=IfCondition(PythonExpression(["'", use_description, "' == 'true' and '", use_rviz, "' != 'true'"])),
            launch_arguments={
                'use_simulation': use_simulation,
                'use_joint_state_publisher': use_joint_state_publisher,
            }.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(f'{pkg_share}/launch/romi_rviz.launch.py'),
            condition=IfCondition(use_rviz),
            launch_arguments={
                'use_simulation': use_simulation,
                'use_joint_state_publisher': use_joint_state_publisher,
            }.items(),
        ),
    ])

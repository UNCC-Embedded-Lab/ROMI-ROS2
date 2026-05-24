#!/usr/bin/env python3

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, PythonExpression
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    romi_pkg_share = get_package_share_directory('romi_base')

    params_file = LaunchConfiguration('params_file')
    use_gazebo = LaunchConfiguration('use_gazebo')
    gazebo_world = LaunchConfiguration('gazebo_world')
    use_lidar = LaunchConfiguration('use_lidar')
    use_description = LaunchConfiguration('use_description')
    use_rviz = LaunchConfiguration('use_rviz')
    use_joint_state_publisher = LaunchConfiguration('use_joint_state_publisher')
    mode = LaunchConfiguration('mode')
    lidar_serial_port = LaunchConfiguration('lidar_serial_port')
    lidar_frame_id = LaunchConfiguration('lidar_frame_id')

    return LaunchDescription([
        DeclareLaunchArgument(
            'params_file',
            default_value=f'{romi_pkg_share}/config/romi_params.yaml',
            description='Path to ROMI parameter file',
        ),
        DeclareLaunchArgument(
            'use_gazebo',
            default_value='false',
            description='Run in Gazebo simulation instead of hardware bringup',
        ),
        DeclareLaunchArgument(
            'gazebo_world',
            default_value=f'{romi_pkg_share}/worlds/romi_simple_gz.sdf',
            description='World file for Gazebo when use_gazebo=true',
        ),
        DeclareLaunchArgument(
            'use_lidar',
            default_value='true',
            description='Launch RPLidar A1 node',
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
            'use_joint_state_publisher',
            default_value='true',
            description='Run joint_state_publisher for model visualization',
        ),
        DeclareLaunchArgument(
            'mode',
            default_value='none',
            description='Robot command source: none | teleop_twist_keyboard | obstacle_avoidance',
        ),
        DeclareLaunchArgument(
            'lidar_serial_port',
            default_value='/dev/ttyUSB0',
            description='Serial device path for RPLidar A1',
        ),
        DeclareLaunchArgument(
            'lidar_frame_id',
            default_value='laser',
            description='Frame id for LaserScan messages',
        ),
        Node(
            package='romi_base',
            executable='astar_bridge',
            name='astar_bridge_node',
            parameters=[params_file],
            condition=IfCondition(PythonExpression(["'", use_gazebo, "' != 'true'"])),
            output='screen',
        ),
        Node(
            package='romi_base',
            executable='base_controller',
            name='base_controller_node',
            parameters=[params_file],
            condition=IfCondition(PythonExpression(["'", use_gazebo, "' != 'true'"])),
            output='screen',
        ),
        Node(
            package='teleop_twist_keyboard',
            executable='teleop_twist_keyboard',
            name='teleop_twist_keyboard',
            condition=IfCondition(PythonExpression(["'", mode, "' == 'teleop_twist_keyboard'"])),
            output='screen',
        ),
        Node(
            package='romi_base',
            executable='obstacle_avoidance',
            name='obstacle_avoidance_node',
            parameters=[params_file],
            condition=IfCondition(PythonExpression(["'", mode, "' == 'obstacle_avoidance'"])),
            output='screen',
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(f'{romi_pkg_share}/launch/romi_description.launch.py'),
            condition=IfCondition(PythonExpression(["'", use_description, "' == 'true' and '", use_rviz, "' != 'true' and '", use_gazebo, "' != 'true'"])),
            launch_arguments={
                'use_simulation': 'false',
                'use_sim_time': 'false',
                'use_joint_state_publisher': use_joint_state_publisher,
            }.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(f'{romi_pkg_share}/launch/romi_rviz.launch.py'),
            condition=IfCondition(PythonExpression(["'", use_rviz, "' == 'true' and '", use_gazebo, "' != 'true'"])),
            launch_arguments={
                'use_simulation': 'false',
                'use_sim_time': 'false',
                'use_joint_state_publisher': use_joint_state_publisher,
            }.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(f'{romi_pkg_share}/launch/romi_gz.launch.py'),
            condition=IfCondition(use_gazebo),
            launch_arguments={
                'world': gazebo_world,
                'mode': mode,
                'use_rviz': use_rviz,
                'rviz_config': f'{romi_pkg_share}/rviz/romi_base.rviz',
            }.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                PathJoinSubstitution([
                    FindPackageShare('rplidar_ros'),
                    'launch',
                    'rplidar_a1_launch.py',
                ])
            ),
            condition=IfCondition(PythonExpression(["'", use_lidar, "' == 'true' and '", use_gazebo, "' != 'true'"])),
            launch_arguments={
                'serial_port': lidar_serial_port,
                'frame_id': lidar_frame_id,
            }.items(),
        ),
    ])

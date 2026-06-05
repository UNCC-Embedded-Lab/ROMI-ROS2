#!/usr/bin/env python3

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, SetEnvironmentVariable
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration, PythonExpression
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory('romi_base')
    ros_gz_sim_share = get_package_share_directory('ros_gz_sim')
    xacro_file = f'{pkg_share}/description/urdf/romi.urdf.xacro'

    world = LaunchConfiguration('world')
    use_rviz = LaunchConfiguration('use_rviz')
    mode = LaunchConfiguration('mode')
    rviz_config = LaunchConfiguration('rviz_config')
    robot_sdf = Command([
        'bash -lc "',
        f'xacro {xacro_file} use_simulation:=true > /tmp/romi_gz_spawn.urdf && gz sdf -p /tmp/romi_gz_spawn.urdf',
        '"',
    ])

    return LaunchDescription([
        DeclareLaunchArgument(
            'world',
            default_value=f'{pkg_share}/worlds/romi_simple_gz.sdf',
            description='Gazebo Sim world file',
        ),
        DeclareLaunchArgument(
            'use_rviz',
            default_value='false',
            description='Launch RViz alongside Gazebo Sim',
        ),
        DeclareLaunchArgument(
            'rviz_config',
            default_value=f'{pkg_share}/rviz/romi_base.rviz',
            description='Path to RViz config file',
        ),
        DeclareLaunchArgument(
            'mode',
            default_value='none',
            description='Robot command source: none | obstacle_avoidance',
        ),
        SetEnvironmentVariable('LIBGL_ALWAYS_SOFTWARE', '1'),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(f'{ros_gz_sim_share}/launch/gz_sim.launch.py'),
            launch_arguments={
                'gz_args': ['-r ', world],
                'on_exit_shutdown': 'true',
            }.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(f'{pkg_share}/launch/romi_description.launch.py'),
            launch_arguments={
                'use_simulation': 'true',
                'use_sim_time': 'true',
            }.items(),
        ),
        Node(
            package='ros_gz_sim',
            executable='create',
            name='spawn_romi_base',
            arguments=[
                '-name', 'romi_base',
                '-string', robot_sdf,
                '-z', '0.08',
            ],
            output='screen',
        ),
        Node(
            package='ros_gz_bridge',
            executable='parameter_bridge',
            name='ros_gz_bridge',
            arguments=[
                '/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock',
                '/cmd_vel@geometry_msgs/msg/Twist]ignition.msgs.Twist',
                '/odom@nav_msgs/msg/Odometry[ignition.msgs.Odometry',
                '/tf@tf2_msgs/msg/TFMessage[ignition.msgs.Pose_V',
                '/joint_states@sensor_msgs/msg/JointState[ignition.msgs.Model',
                '/scan@sensor_msgs/msg/LaserScan[ignition.msgs.LaserScan',
            ],
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
            parameters=[{'use_sim_time': True}],
            output='screen',
        ),
    ])

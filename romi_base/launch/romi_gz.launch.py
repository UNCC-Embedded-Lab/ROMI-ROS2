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
    use_gazebo_gui = LaunchConfiguration('use_gazebo_gui')
    use_rviz = LaunchConfiguration('use_rviz')
    rviz_config = LaunchConfiguration('rviz_config')
    robot_sdf = Command([
        'bash -lc "',
        f'xacro {xacro_file} use_simulation:=true > /tmp/romi_gz_spawn.urdf && ign sdf -p /tmp/romi_gz_spawn.urdf',
        '"',
    ])
    robot_description = {
        'robot_description': Command(['xacro ', xacro_file, ' use_simulation:=true'])
    }

    return LaunchDescription([
        DeclareLaunchArgument(
            'world',
            default_value=f'{pkg_share}/worlds/romi_office_gz.sdf',
            description='Gazebo Sim world file',
        ),
        DeclareLaunchArgument(
            'use_gazebo_gui',
            default_value='true',
            description='Run Gazebo with GUI when true, server-only when false',
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
        SetEnvironmentVariable('LIBGL_ALWAYS_SOFTWARE', '1'),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(f'{ros_gz_sim_share}/launch/gz_sim.launch.py'),
            condition=IfCondition(use_gazebo_gui),
            launch_arguments={
                'gz_args': ['-r ', world],
                'on_exit_shutdown': 'true',
            }.items(),
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(f'{ros_gz_sim_share}/launch/gz_sim.launch.py'),
            condition=IfCondition(PythonExpression(["'", use_gazebo_gui, "' != 'true'"])),
            launch_arguments={
                'gz_args': ['-r -s ', world],
                'on_exit_shutdown': 'true',
            }.items(),
        ),
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            parameters=[robot_description, {'publish_robot_description': True, 'use_sim_time': True}],
            output='screen',
        ),
        Node(
            package='joint_state_publisher',
            executable='joint_state_publisher',
            name='joint_state_publisher',
            parameters=[robot_description, {'use_gui': False, 'use_sim_time': True}],
            output='screen',
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
        # Ignition Gazebo 6 merges fixed URDF links into base_link during URDF->SDF
        # conversion, so the lidar sensor ends up scoped as romi_base/base_link/laser.
        # This static transform bridges that Ignition frame name to the URDF TF frame.
        Node(
            package='tf2_ros',
            executable='static_transform_publisher',
            name='lidar_frame_bridge',
            arguments=['0', '0', '0', '0', '0', '0', 'lidar_frame', 'romi_base/base_link/laser'],
            parameters=[{'use_sim_time': True}],
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

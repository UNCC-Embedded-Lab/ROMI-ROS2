import os
from glob import glob

from setuptools import find_packages, setup

package_name = 'romi_base'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
        (os.path.join('share', package_name, 'rviz'), glob('rviz/*.rviz')),
        (os.path.join('share', package_name, 'worlds'), glob('worlds/*.sdf')),
        (os.path.join('share', package_name, 'maps'), glob('maps/*')),
        (os.path.join('share', package_name, 'description', 'urdf'), glob('description/urdf/*')),
        (os.path.join('share', package_name, 'description', 'meshes'), glob('description/meshes/*')),
        (os.path.join('share', package_name, 'description'), glob('description/*.md')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='brett',
    maintainer_email='brettnguyen.engr@gmail.com',
    description='Unified ROMI robot bringup and control nodes',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'astar_bridge = romi_base.astar_bridge_node:main',
            'base_controller = romi_base.base_controller_node:main',
            'obstacle_avoidance = romi_base.obstacle_avoidance_node:main',
            'square_test_node = romi_base.square_test_node:main',
        ],
    },
)

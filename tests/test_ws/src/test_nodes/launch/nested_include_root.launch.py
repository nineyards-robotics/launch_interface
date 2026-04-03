"""Test case: Root of a nested include chain (root -> mid -> included)."""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    mid_file = os.path.join(
        get_package_share_directory('test_nodes'),
        'launch',
        'nested_include_mid.launch.py',
    )

    return LaunchDescription([
        Node(
            package='test_nodes',
            executable='node_a',
            name='root_node',
            namespace='/root_ns',
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(mid_file),
            launch_arguments={'mid_name': 'custom_mid'}.items(),
        ),
    ])

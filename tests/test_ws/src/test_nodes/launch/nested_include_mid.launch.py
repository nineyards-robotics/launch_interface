"""Test case: Mid-level file in a nested include chain (root -> mid -> included)."""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    included_file = os.path.join(
        get_package_share_directory('test_nodes'),
        'launch',
        'included.launch.py',
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'mid_name',
            default_value='mid_default',
            description='Name for the mid-level node',
        ),
        Node(
            package='test_nodes',
            executable='node_a',
            name=LaunchConfiguration('mid_name'),
            namespace='/mid_ns',
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(included_file),
            launch_arguments={'child_name': 'nested_child'}.items(),
        ),
    ])

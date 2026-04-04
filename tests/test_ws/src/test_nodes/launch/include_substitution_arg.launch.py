"""Test case: Include with LaunchConfiguration substitution as argument value.

Reproduces the bug where a LaunchConfiguration object passed as an include
argument value is not resolved, producing a repr string like
``<launch.substitutions.launch_configuration.LaunchConfiguration object at 0x...>``
instead of the actual value.
"""
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
            'child_name',
            default_value='substituted_child',
            description='Name passed through as a LaunchConfiguration substitution',
        ),
        Node(
            package='test_nodes',
            executable='node_a',
            name='parent_node',
            namespace='/parent_ns',
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(included_file),
            launch_arguments=[
                ('child_name', LaunchConfiguration('child_name')),
            ],
        ),
    ])

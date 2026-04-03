"""Test case 4 (parent): Include chain — includes included.launch.py."""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    included_file = os.path.join(
        get_package_share_directory('test_nodes'),
        'launch',
        'included.launch.py',
    )

    return LaunchDescription([
        Node(
            package='test_nodes',
            executable='node_a',
            name='parent_node',
            namespace='/parent_ns',
        ),
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(included_file),
            launch_arguments={'child_name': 'included_child'}.items(),
        ),
    ])

"""Test case: Python launch file including an XML launch file."""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import AnyLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    xml_file = os.path.join(
        get_package_share_directory('test_nodes'),
        'launch',
        'simple_node.launch.xml',
    )

    return LaunchDescription([
        Node(
            package='test_nodes',
            executable='node_a',
            name='python_node',
            namespace='/test_ns',
        ),
        IncludeLaunchDescription(
            AnyLaunchDescriptionSource(xml_file),
        ),
    ])

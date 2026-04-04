"""Test case 20: Node without a name specified."""
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='test_nodes',
            executable='node_a',
            namespace='/test_ns',
        ),
    ])

"""Test case 1: Simple single node."""
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='test_nodes',
            executable='node_a',
            name='my_node',
            namespace='/test_ns',
        ),
    ])

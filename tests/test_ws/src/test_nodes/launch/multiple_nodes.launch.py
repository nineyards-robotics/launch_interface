"""Test case: Multiple nodes in a single launch file."""
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='test_nodes',
            executable='node_a',
            name='first',
            namespace='/ns_a',
        ),
        Node(
            package='test_nodes',
            executable='node_b',
            name='second',
            namespace='/ns_b',
        ),
        Node(
            package='test_nodes',
            executable='node_a',
            name='third',
            namespace='/ns_a',
        ),
    ])

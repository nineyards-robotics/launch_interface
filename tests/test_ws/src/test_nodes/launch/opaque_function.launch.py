"""Test case: Dynamic node creation via OpaqueFunction."""
from launch import LaunchDescription
from launch.actions import OpaqueFunction
from launch_ros.actions import Node


def _create_node(context):
    return [
        Node(
            package='test_nodes',
            executable='node_a',
            name='dynamic_node',
            namespace='/test_ns',
        ),
    ]


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='test_nodes',
            executable='node_b',
            name='static_node',
            namespace='/test_ns',
        ),
        OpaqueFunction(function=_create_node),
    ])

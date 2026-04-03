"""Test case: Node name resolved from an environment variable."""
from launch import LaunchDescription
from launch.substitutions import EnvironmentVariable
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='test_nodes',
            executable='node_a',
            name=EnvironmentVariable('TEST_NODE_NAME'),
            namespace='/test_ns',
        ),
    ])

"""Test case: Raw ExecuteProcess alongside a Node."""
from launch import LaunchDescription
from launch.actions import ExecuteProcess
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        ExecuteProcess(
            cmd=['echo', 'hello'],
            name='my_process',
        ),
        Node(
            package='test_nodes',
            executable='node_a',
            name='real_node',
            namespace='/test_ns',
        ),
    ])

"""Test case 6: Conditional nodes using IfCondition / UnlessCondition."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            'use_node_b',
            default_value='true',
            description='Whether to launch node_b',
        ),
        Node(
            package='test_nodes',
            executable='node_a',
            name='always_node',
            namespace='/test_ns',
        ),
        Node(
            package='test_nodes',
            executable='node_b',
            name='conditional_node',
            namespace='/test_ns',
            condition=IfCondition(LaunchConfiguration('use_node_b')),
        ),
        Node(
            package='test_nodes',
            executable='node_a',
            name='unless_node',
            namespace='/test_ns',
            condition=UnlessCondition(LaunchConfiguration('use_node_b')),
        ),
    ])

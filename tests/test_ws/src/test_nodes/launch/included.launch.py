"""Test case 4 (child): Included launch file with a declared argument."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            'child_name',
            default_value='child_default',
            description='Name for the child node',
        ),
        Node(
            package='test_nodes',
            executable='node_b',
            name=LaunchConfiguration('child_name'),
            namespace='/child_ns',
        ),
    ])

"""Test case: Required launch argument with no default."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            'required_param',
            description='A required parameter with no default',
        ),
        Node(
            package='test_nodes',
            executable='node_a',
            name=LaunchConfiguration('required_param'),
            namespace='/test_ns',
        ),
    ])

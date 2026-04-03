"""Test case 3: Remappings and launch arguments."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            'node_name',
            default_value='default_node',
            description='Name for the node',
        ),
        DeclareLaunchArgument(
            'input_topic',
            default_value='/default_input',
            description='Input topic to remap',
        ),
        Node(
            package='test_nodes',
            executable='node_a',
            name=LaunchConfiguration('node_name'),
            namespace='/test_ns',
            remappings=[
                ('input', LaunchConfiguration('input_topic')),
                ('output', '/global_output'),
            ],
        ),
    ])

"""Test case 2: Node with parameters from file and inline."""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    params_file = os.path.join(
        get_package_share_directory('test_nodes'),
        'params',
        'test_params.yaml',
    )

    return LaunchDescription([
        Node(
            package='test_nodes',
            executable='node_a',
            name='param_node',
            namespace='/test_ns',
            parameters=[
                params_file,
                {'inline_param': 'hello', 'inline_int': 42},
            ],
        ),
    ])

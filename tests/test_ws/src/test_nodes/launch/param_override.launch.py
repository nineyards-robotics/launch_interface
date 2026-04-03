"""Test case: Parameter merge order — wildcard, node-specific, then inline override."""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    params_file = os.path.join(
        get_package_share_directory('test_nodes'),
        'params',
        'override_params.yaml',
    )

    return LaunchDescription([
        Node(
            package='test_nodes',
            executable='node_a',
            name='override_node',
            namespace='/test_ns',
            parameters=[
                params_file,
                {'shared_param': 'from_inline'},
            ],
        ),
    ])

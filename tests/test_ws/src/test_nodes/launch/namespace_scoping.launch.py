"""Test case 9: Namespace scoping via GroupAction + PushRosNamespace."""
from launch import LaunchDescription
from launch.actions import GroupAction
from launch_ros.actions import Node, PushRosNamespace


def generate_launch_description():
    return LaunchDescription([
        Node(
            package='test_nodes',
            executable='node_a',
            name='outer_node',
            namespace='/root_ns',
        ),
        GroupAction([
            PushRosNamespace('inner_ns'),
            Node(
                package='test_nodes',
                executable='node_b',
                name='inner_node',
            ),
        ]),
    ])

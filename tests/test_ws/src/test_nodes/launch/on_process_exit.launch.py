"""Test case: Node launched via OnProcessExit event handler."""
from launch import LaunchDescription
from launch.actions import RegisterEventHandler
from launch.event_handlers import OnProcessExit
from launch_ros.actions import Node


def generate_launch_description():
    first_node = Node(
        package='test_nodes',
        executable='node_a',
        name='first_node',
        namespace='/test_ns',
    )
    exit_triggered_node = Node(
        package='test_nodes',
        executable='node_b',
        name='exit_triggered_node',
        namespace='/test_ns',
    )

    return LaunchDescription([
        first_node,
        RegisterEventHandler(
            OnProcessExit(
                target_action=first_node,
                on_exit=[exit_triggered_node],
            )
        ),
    ])

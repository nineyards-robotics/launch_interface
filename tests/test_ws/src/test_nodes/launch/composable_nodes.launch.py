"""Test case 5: Composable node container with loaded components."""
from launch import LaunchDescription
from launch_ros.actions import ComposableNodeContainer, LoadComposableNodes
from launch_ros.descriptions import ComposableNode


def generate_launch_description():
    return LaunchDescription([
        ComposableNodeContainer(
            name='my_container',
            namespace='/test_ns',
            package='rclcpp_components',
            executable='component_container',
        ),
        LoadComposableNodes(
            target_container='/test_ns/my_container',
            composable_node_descriptions=[
                ComposableNode(
                    package='composition',
                    plugin='composition::Talker',
                    name='talker',
                    namespace='/test_ns',
                ),
                ComposableNode(
                    package='composition',
                    plugin='composition::Listener',
                    name='listener',
                    namespace='/test_ns',
                    parameters=[{'use_sim_time': True}],
                    remappings=[('chatter', '/custom_chatter')],
                ),
            ],
        ),
    ])

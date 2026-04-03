"""Minimal dummy node for testing."""
import rclpy
from rclpy.node import Node


class NodeA(Node):
    def __init__(self):
        super().__init__('node_a')


def main(args=None):
    rclpy.init(args=args)
    node = NodeA()
    rclpy.spin(node)
    rclpy.shutdown()


if __name__ == '__main__':
    main()

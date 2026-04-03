"""Minimal dummy node for testing."""
import rclpy
from rclpy.node import Node


class NodeB(Node):
    def __init__(self):
        super().__init__('node_b')


def main(args=None):
    rclpy.init(args=args)
    node = NodeB()
    rclpy.spin(node)
    rclpy.shutdown()


if __name__ == '__main__':
    main()

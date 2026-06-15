#!/usr/bin/env python3

import time

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist


class SquareTestNode(Node):
    def __init__(self):
        super().__init__('square_test_node')

        self.cmd_pub = self.create_publisher(Twist, '/cmd_vel', 10)

        # Commanded robot velocities
        self.forward_speed = 0.10      # meters per second
        self.turn_speed = 0.75         # radians per second

        # Desired square dimensions
        self.side_length = 0.6096      # meters, equal to 2 ft
        self.turn_angle = 1.5708       # radians, equal to 90 degrees

        # Motion durations are calculated from commanded velocities.
        # Tune the velocity controller, not these timing calculations.
        self.forward_time = self.side_length / self.forward_speed
        self.turn_time = self.turn_angle / self.turn_speed

        self.get_logger().info('Square test node started.')
        self.get_logger().info(f'Forward time: {self.forward_time:.2f} seconds')
        self.get_logger().info(f'Turn time: {self.turn_time:.2f} seconds')

        time.sleep(2.0)

        self.drive_square()
        self.stop_robot()

        self.get_logger().info('Square test complete.')

    def publish_cmd_for_duration(self, linear_x, angular_z, duration):
        msg = Twist()
        msg.linear.x = linear_x
        msg.angular.z = angular_z

        start_time = time.time()

        while time.time() - start_time < duration:
            self.cmd_pub.publish(msg)
            time.sleep(0.05)

        self.stop_robot()
        time.sleep(0.5)

    def stop_robot(self):
        msg = Twist()
        msg.linear.x = 0.0
        msg.angular.z = 0.0

        for _ in range(10):
            self.cmd_pub.publish(msg)
            time.sleep(0.05)

    def drive_square(self):
        for side in range(4):
            self.get_logger().info(f'Driving side {side + 1}')
            self.publish_cmd_for_duration(self.forward_speed, 0.0, self.forward_time)

            self.get_logger().info(f'Turning corner {side + 1}')
            self.publish_cmd_for_duration(0.0, self.turn_speed, self.turn_time)


def main(args=None):
    rclpy.init(args=args)
    node = SquareTestNode()
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
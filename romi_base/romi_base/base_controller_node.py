import math

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import TransformStamped, Twist
from nav_msgs.msg import Odometry
from std_msgs.msg import Int16MultiArray, Int32MultiArray
from tf2_ros import TransformBroadcaster


class BaseControllerNode(Node):
    def __init__(self):
        super().__init__('base_controller_node')

        # Parameters are preserved so launch/config files continue to work.
        # Students can tune values in YAML without editing this node.
        self.declare_parameter('wheel_base_m', 0.141)
        self.declare_parameter('wheel_diameter_m', 0.07)
        self.declare_parameter('ticks_per_rev_wheel', 1440.0)
        self.declare_parameter('kp', 600.0)
        self.declare_parameter('ki', 400.0)
        self.declare_parameter('max_pwm', 300.0)

        # ROS interfaces are preserved for the lab scaffold.
        # Keep these topic names unchanged so existing launch files still work.
        self.create_subscription(Twist, '/cmd_vel', self.twist_callback, 10)
        self.create_subscription(
            Int32MultiArray,
            '/encoder_ticks',
            self.encoder_callback,
            10,
        )
        self.pwm_pub = self.create_publisher(Int16MultiArray, '/wheel_pwm', 10)
        self.odom_pub = self.create_publisher(Odometry, '/odom', 10)
        self.tf_broadcaster = TransformBroadcaster(self)

        # Robot constants used by later lab steps.
        self.wheel_base = float(self.get_parameter('wheel_base_m').value)
        wheel_diameter = float(self.get_parameter('wheel_diameter_m').value)
        self.wheel_circumference = math.pi * wheel_diameter
        self.ticks_per_rev_wheel = float(self.get_parameter('ticks_per_rev_wheel').value)

        # Control gains are kept for future PI-control exercises.
        self.kp = float(self.get_parameter('kp').value)
        self.ki = float(self.get_parameter('ki').value)
        self.max_pwm = float(self.get_parameter('max_pwm').value)

        # State placeholders students will extend.
        # Targets are wheel linear speeds in meters/second.
        self.target_left_mps = 0.0
        self.target_right_mps = 0.0
        # Integrator state for the PI controller exercise.
        self.integral_left = 0.0
        self.integral_right = 0.0

        # Previous encoder samples used to compute tick deltas.
        self.prev_left_ticks = None
        self.prev_right_ticks = None
        self.last_time = self.get_clock().now()

        # Odometry pose state in the odom frame.
        self.x = 0.0
        self.y = 0.0
        self.theta = 0.0

        self.get_logger().info('ROMI Base Controller lab starter initialized.')

    def twist_callback(self, msg: Twist):
        # TODO (lab): convert cmd_vel (v, w) into target wheel speeds.
        # For the starter branch, we intentionally do nothing.
        _ = msg

    def encoder_callback(self, msg: Int32MultiArray):
        current_time = self.get_clock().now()
        dt = (current_time - self.last_time).nanoseconds / 1e9
        self.last_time = current_time

        if len(msg.data) < 2:
            self.get_logger().warn('Expected 2 encoder ticks: [left, right].')
            return

        current_left = msg.data[0]
        current_right = msg.data[1]

        if self.prev_left_ticks is None:
            self.prev_left_ticks = current_left
            self.prev_right_ticks = current_right
            self.publish_odometry(current_time, 0.0, 0.0)
            return

        # TODO (lab): compute wrapped delta ticks.
        # Calls are commented out in starter mode so this node runs even before
        # students implement rollover logic in calculate_delta().
        # delta_left = self.calculate_delta(current_left, self.prev_left_ticks)
        # delta_right = self.calculate_delta(current_right, self.prev_right_ticks)
        delta_left = 0
        delta_right = 0

        self.prev_left_ticks = current_left
        self.prev_right_ticks = current_right

        # TODO (lab): convert ticks to wheel distances/speeds and apply PI control.
        # Keep placeholder variables for future exercises and to avoid lint noise.
        _ = dt
        _ = delta_left
        _ = delta_right

        pwm_msg = Int16MultiArray()
        # Starter behavior: publish neutral PWM so motors remain stopped.
        pwm_msg.data = [0, 0]
        self.pwm_pub.publish(pwm_msg)

        # TODO (lab): integrate odometry from wheel distances.
        # Starter behavior: publish static pose and zero twist.
        self.publish_odometry(current_time, 0.0, 0.0)

    def publish_odometry(self, current_time, v: float, w: float):
        q_z = math.sin(self.theta / 2.0)
        q_w = math.cos(self.theta / 2.0)

        t = TransformStamped()
        t.header.stamp = current_time.to_msg()
        t.header.frame_id = 'odom'
        t.child_frame_id = 'base_link'
        t.transform.translation.x = self.x
        t.transform.translation.y = self.y
        t.transform.translation.z = 0.0
        t.transform.rotation.x = 0.0
        t.transform.rotation.y = 0.0
        t.transform.rotation.z = q_z
        t.transform.rotation.w = q_w
        self.tf_broadcaster.sendTransform(t)

        odom = Odometry()
        odom.header.stamp = current_time.to_msg()
        odom.header.frame_id = 'odom'
        odom.child_frame_id = 'base_link'
        odom.pose.pose.position.x = self.x
        odom.pose.pose.position.y = self.y
        odom.pose.pose.orientation.z = q_z
        odom.pose.pose.orientation.w = q_w
        odom.twist.twist.linear.x = v
        odom.twist.twist.angular.z = w
        self.odom_pub.publish(odom)

    def calculate_pi_pwm(self, error: float, dt: float, side: str) -> float:
        # TODO (lab): implement PI controller with anti-windup and clamping.
        # Returning zero keeps the starter node safe and deterministic.
        _ = error
        _ = dt
        _ = side
        return 0.0

    def calculate_delta(self, current: int, prev: int) -> int:
        # TODO (lab): implement encoder wrap handling for int16 rollover.
        # Returning zero keeps startup behavior simple until lab completion.
        _ = current
        _ = prev
        return 0


def main(args=None):
    rclpy.init(args=args)
    node = BaseControllerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

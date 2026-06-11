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

    def _get_wheel_speed_targets(self, linear_x: float, angular_z: float):
        half_wheel_base = self.wheel_base / 2.0
        left_target = linear_x - angular_z * half_wheel_base
        right_target = linear_x + angular_z * half_wheel_base
        return left_target, right_target

    def _clamp(self, value: float, lower: float, upper: float) -> float:
        return max(lower, min(upper, value))

    def _normalize_angle(self, angle: float) -> float:
        return math.atan2(math.sin(angle), math.cos(angle))

    def twist_callback(self, msg: Twist):
        self.target_left_mps, self.target_right_mps = self._get_wheel_speed_targets(
            float(msg.linear.x),
            float(msg.angular.z),
        )

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

        delta_left = self.calculate_delta(current_left, self.prev_left_ticks)
        delta_right = self.calculate_delta(current_right, self.prev_right_ticks)

        self.prev_left_ticks = current_left
        self.prev_right_ticks = current_right

        if dt <= 0.0:
            dt = 1e-6

        left_distance = (delta_left / self.ticks_per_rev_wheel) * self.wheel_circumference
        right_distance = (delta_right / self.ticks_per_rev_wheel) * self.wheel_circumference
        measured_left_mps = left_distance / dt
        measured_right_mps = right_distance / dt

        left_pwm = self.calculate_pi_pwm(self.target_left_mps - measured_left_mps, dt, 'left')
        right_pwm = self.calculate_pi_pwm(self.target_right_mps - measured_right_mps, dt, 'right')

        pwm_msg = Int16MultiArray()
        pwm_msg.data = [int(round(left_pwm)), int(round(right_pwm))]
        self.pwm_pub.publish(pwm_msg)

        linear_distance = 0.5 * (left_distance + right_distance)
        angular_distance = (right_distance - left_distance) / self.wheel_base
        theta_mid = self.theta + angular_distance / 2.0
        self.x += linear_distance * math.cos(theta_mid)
        self.y += linear_distance * math.sin(theta_mid)
        self.theta = self._normalize_angle(self.theta + angular_distance)

        actual_linear = linear_distance / dt
        actual_angular = angular_distance / dt
        self.publish_odometry(current_time, actual_linear, actual_angular)

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
        proportional = self.kp * error

        if side == 'left':
            self.integral_left += error * dt
            integral_term = self.ki * self.integral_left
        else:
            self.integral_right += error * dt
            integral_term = self.ki * self.integral_right

        raw_pwm = proportional + integral_term
        clamped_pwm = self._clamp(raw_pwm, -self.max_pwm, self.max_pwm)

        if clamped_pwm != raw_pwm and self.ki != 0.0:
            if side == 'left':
                self.integral_left = (clamped_pwm - proportional) / self.ki
            else:
                self.integral_right = (clamped_pwm - proportional) / self.ki

        return clamped_pwm

    def calculate_delta(self, current: int, prev: int) -> int:
        delta = current - prev
        rollover_span = 1 << 16
        rollover_threshold = 1 << 15

        if delta > rollover_threshold:
            delta -= rollover_span
        elif delta < -rollover_threshold:
            delta += rollover_span

        return delta


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

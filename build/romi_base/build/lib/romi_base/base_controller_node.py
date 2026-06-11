import rclpy
from rclpy.node import Node
import math

from geometry_msgs.msg import Twist, TransformStamped
from std_msgs.msg import Int32MultiArray, Int16MultiArray
from nav_msgs.msg import Odometry
from tf2_ros import TransformBroadcaster

class BaseControllerNode(Node):
    def __init__(self):
        super().__init__('base_controller_node')

        self.declare_parameter('wheel_base_m', 0.141)
        self.declare_parameter('wheel_diameter_m', 0.07)
        self.declare_parameter('ticks_per_rev_wheel', 1440.0)
        self.declare_parameter('kp', 600.0)
        self.declare_parameter('ki', 400.0)
        self.declare_parameter('max_pwm', 300.0)
        
        # --- ROS 2 INTERFACES ---
        self.create_subscription(Twist, '/cmd_vel', self.twist_callback, 10)
        self.create_subscription(Int32MultiArray, '/encoder_ticks', self.encoder_callback, 10)
        
        self.pwm_pub = self.create_publisher(Int16MultiArray, '/wheel_pwm', 10)
        self.odom_pub = self.create_publisher(Odometry, '/odom', 10)
        self.tf_broadcaster = TransformBroadcaster(self)
        
        # --- ROBOT CONSTANTS ---
        self.wheel_base = float(self.get_parameter('wheel_base_m').value)
        wheel_diameter = float(self.get_parameter('wheel_diameter_m').value)
        self.wheel_circumference = math.pi * wheel_diameter
        self.ticks_per_rev_wheel = float(self.get_parameter('ticks_per_rev_wheel').value)
        
        # --- TUNING PARAMETERS ---
        self.Kp = float(self.get_parameter('kp').value)
        self.Ki = float(self.get_parameter('ki').value)
        self.max_pwm = float(self.get_parameter('max_pwm').value)
        
        # --- INTERNAL STATE VARIABLES ---
        self.target_left_mps = 0.0
        self.target_right_mps = 0.0
        self.integral_left = 0.0
        self.integral_right = 0.0
        
        self.prev_left_ticks = None
        self.prev_right_ticks = None
        self.last_time = self.get_clock().now()
        
        # Odometry State
        self.x = 0.0
        self.y = 0.0
        self.theta = 0.0
        
        self.get_logger().info("ROMI Base Controller (Kinematics + PI + Odometry) Initialized.")

    def twist_callback(self, msg):
        v = msg.linear.x
        omega = msg.angular.z
        self.target_left_mps = v - (omega * self.wheel_base / 2.0)
        self.target_right_mps = v + (omega * self.wheel_base / 2.0)

    def encoder_callback(self, msg):
        current_time = self.get_clock().now()
        dt = (current_time - self.last_time).nanoseconds / 1e9
        self.last_time = current_time
        
        current_left = msg.data[0]
        current_right = msg.data[1]
        
        if self.prev_left_ticks is None:
            self.prev_left_ticks = current_left
            self.prev_right_ticks = current_right
            return
            
        # Delta Ticks
        delta_left = self.calculate_delta(current_left, self.prev_left_ticks)
        delta_right = self.calculate_delta(current_right, self.prev_right_ticks)
        
        self.prev_left_ticks = current_left
        self.prev_right_ticks = current_right
        
        # Distance per wheel (meters)
        d_left = (delta_left / self.ticks_per_rev_wheel) * self.wheel_circumference
        d_right = (delta_right / self.ticks_per_rev_wheel) * self.wheel_circumference
        
        # ---------------------------------------------------------
        # SECTION A: PI CONTROL
        # ---------------------------------------------------------
        actual_left_mps = d_left / dt if dt > 0 else 0.0
        actual_right_mps = d_right / dt if dt > 0 else 0.0
        
        error_left = self.target_left_mps - actual_left_mps
        error_right = self.target_right_mps - actual_right_mps
        
        pwm_left = self.calculate_pi_pwm(error_left, dt, 'left')
        pwm_right = self.calculate_pi_pwm(error_right, dt, 'right')
        
        pwm_msg = Int16MultiArray()
        pwm_msg.data = [int(pwm_left), int(pwm_right)]
        self.pwm_pub.publish(pwm_msg)
        
        # ---------------------------------------------------------
        # SECTION B: ODOMETRY AND TF
        # ---------------------------------------------------------
        delta_s = (d_right + d_left) / 2.0
        delta_theta = (d_right - d_left) / self.wheel_base
        
        self.x += delta_s * math.cos(self.theta + (delta_theta / 2.0))
        self.y += delta_s * math.sin(self.theta + (delta_theta / 2.0))
        self.theta += delta_theta
        
        v = delta_s / dt if dt > 0 else 0.0
        w = delta_theta / dt if dt > 0 else 0.0
        
        self.publish_odometry(current_time, v, w)

    def publish_odometry(self, current_time, v, w):
        q_z = math.sin(self.theta / 2.0)
        q_w = math.cos(self.theta / 2.0)

        # Publish TF
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

        # Publish Odom
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

    def calculate_pi_pwm(self, error, dt, side):
        if side == 'left':
            self.integral_left += error * dt
            integral = self.integral_left
        else:
            self.integral_right += error * dt
            integral = self.integral_right
            
        pwm = (self.Kp * error) + (self.Ki * integral)
        
        if pwm > self.max_pwm:
            pwm = self.max_pwm
            if side == 'left': self.integral_left -= error * dt
            else: self.integral_right -= error * dt
        elif pwm < -self.max_pwm:
            pwm = -self.max_pwm
            if side == 'left': self.integral_left -= error * dt
            else: self.integral_right -= error * dt
            
        return pwm

    def calculate_delta(self, current, prev):
        delta = current - prev
        if delta > 32767:
            delta -= 65536
        elif delta < -32768:
            delta += 65536
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
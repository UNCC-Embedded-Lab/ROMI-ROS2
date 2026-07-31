import math

import rclpy
from rclpy.node import Node
from std_msgs.msg import Int16MultiArray, Int32MultiArray
from sensor_msgs.msg import Imu
from .astar_interface import AStarInterface
from .lsm6_interface import Lsm6Interface

# LSM6DS33 default enableDefault() sensitivities (see lsm6-arduino library):
#   accel: +-2 g full scale  -> 0.061 mg/LSB
#   gyro:  +-245 dps full scale -> 8.75 mdps/LSB
ACCEL_SCALE = 0.061e-3 * 9.80665  # raw LSB -> m/s^2
GYRO_SCALE = 8.75e-3 * (math.pi / 180.0)  # raw LSB -> rad/s

class AStarBridgeNode(Node):
    def __init__(self):
        super().__init__('astar_bridge_node')

        self.declare_parameter('encoder_rate_hz', 50.0)
        self.declare_parameter('imu_rate_hz', 50.0)
        self.declare_parameter('imu_frame_id', 'base_link')
        
        # Initialize the hardware interface
        self.romi = AStarInterface()

        # The LSM6DS33 is read directly over I2C at its own address
        # (it is not relayed through the AVR's slave buffer - see the
        # note in RomiRPiSlaveDemo.ino and lsm6_interface.py).
        self.imu = Lsm6Interface()
        self.imu_detected = self.imu.init()
        if self.imu_detected:
            self.imu.enable_default()
        else:
            self.get_logger().warn("LSM6DS33 not detected; /imu/data_raw will not be published.")

        # Subscribe to LED commands (from Laptop node)
        self.led_subscription = self.create_subscription(
            Int16MultiArray,
            '/leds',
            self.led_callback,
            10
        )

        # Subscribe to pwm commands (from PI node)
        self.subscription = self.create_subscription(
            Int16MultiArray,
            '/wheel_pwm',
            self.pwm_callback,
            10
        )

        # Publisher for encoder ticks
        self.encoder_pub = self.create_publisher(
            Int32MultiArray,
            '/encoder_ticks',
            10
        )

        # Publisher for raw IMU data (accel + gyro, no orientation estimate)
        self.imu_pub = self.create_publisher(
            Imu,
            '/imu/data_raw',
            10
        )

        # Read encoders at configured rate
        encoder_rate_hz = float(self.get_parameter('encoder_rate_hz').value)
        period = 1.0 / encoder_rate_hz if encoder_rate_hz > 0.0 else 0.02
        self.timer = self.create_timer(period, self.read_encoders)

        # Read IMU at configured rate
        self.imu_frame_id = str(self.get_parameter('imu_frame_id').value)
        imu_rate_hz = float(self.get_parameter('imu_rate_hz').value)
        imu_period = 1.0 / imu_rate_hz if imu_rate_hz > 0.0 else 0.02
        self.imu_timer = self.create_timer(imu_period, self.read_imu)
        
        # Safety: Ensure motors start at 0
        self.romi.motors(0, 0)

        self.get_logger().info("AStar I2C Interface Initialized.")

    def led_callback(self, msg):
        # Ensure we received an array of 3 values
        if len(msg.data) >= 3:
            red = int(msg.data[0])
            yellow = int(msg.data[1])
            green = int(msg.data[2])
            
            try:
                self.romi.leds(red, yellow, green)
            except OSError as e:
                self.get_logger().error(f"I2C LED error: {e}")

    def pwm_callback(self, msg):
        left_pwm = int(msg.data[0])
        right_pwm = int(msg.data[1])
        try:
            self.romi.motors(left_pwm, right_pwm)
        except OSError as e:
            self.get_logger().error(f"I2C PWM error: {e}")

    def read_encoders(self):
        # astar_interface.py unpacks using 'hh' returning 2 32-bit integers
        try:
            left_ticks, right_ticks = self.romi.read_encoders()

            msg = Int32MultiArray()
            msg.data = [int(left_ticks), int(right_ticks)]
            self.encoder_pub.publish(msg)
        except OSError as e:
            self.get_logger().error(f"I2C Encoder Read Error: {e}")

    def read_imu(self):
        if not self.imu_detected:
            return

        try:
            ax, ay, az, gx, gy, gz = self.imu.read()

            msg = Imu()
            msg.header.stamp = self.get_clock().now().to_msg()
            msg.header.frame_id = self.imu_frame_id

            msg.linear_acceleration.x = ax * ACCEL_SCALE
            msg.linear_acceleration.y = ay * ACCEL_SCALE
            msg.linear_acceleration.z = az * ACCEL_SCALE

            msg.angular_velocity.x = gx * GYRO_SCALE
            msg.angular_velocity.y = gy * GYRO_SCALE
            msg.angular_velocity.z = gz * GYRO_SCALE

            # No orientation estimate is provided by this bridge.
            msg.orientation_covariance[0] = -1.0

            self.imu_pub.publish(msg)
        except OSError as e:
            self.get_logger().error(f"I2C IMU Read Error: {e}")

def main(args=None):
    rclpy.init(args=args)
    node = AStarBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        # Safety: Stop motors when the node is killed
        node.romi.motors(0, 0)
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
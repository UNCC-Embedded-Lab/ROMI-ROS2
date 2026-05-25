import rclpy
from rclpy.node import Node
from std_msgs.msg import Int16MultiArray, Int32MultiArray
from .astar_interface import AStarInterface

class AStarBridgeNode(Node):
    def __init__(self):
        super().__init__('astar_bridge_node')

        self.declare_parameter('encoder_rate_hz', 50.0)
        
        # Initialize the hardware interface
        self.romi = AStarInterface()

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

        # Read encoders at configured rate
        encoder_rate_hz = float(self.get_parameter('encoder_rate_hz').value)
        period = 1.0 / encoder_rate_hz if encoder_rate_hz > 0.0 else 0.02
        self.timer = self.create_timer(period, self.read_encoders)
        
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
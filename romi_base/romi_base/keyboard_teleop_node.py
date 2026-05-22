import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
import sys, select, termios, tty

# Key mapping: {key: (linear.x, angular.z)}
KEY_BINDINGS = {
    'w': ( 0.20,  0.0), # Forward
    's': (-0.20,  0.0), # Backward
    'a': ( 0.0,  1.0), # Spin Left (Counter-Clockwise)
    'd': ( 0.0, -1.0), # Spin Right (Clockwise)
    ' ': ( 0.0,  0.0), # STOP (Spacebar)
}

class KeyboardTeleopNode(Node):
    def __init__(self):
        super().__init__('keyboard_teleop_node')
        self.publisher = self.create_publisher(Twist, '/cmd_vel', 10)
        self.settings = termios.tcgetattr(sys.stdin)
        self.get_logger().info("Keyboard Teleop Node Started. Use W/A/S/D to move, Space to stop, Ctrl+C to quit.")

    def get_key(self):
        # Magic to read a single keypress from the terminal without pressing Enter
        tty.setraw(sys.stdin.fileno())
        select.select([sys.stdin], [], [], 0)
        key = sys.stdin.read(1)
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.settings)
        return key

    def run(self):
        twist_msg = Twist()
        try:
            while rclpy.ok():
                key = self.get_key()
                
                if key == '\x03': # Ctrl+C
                    break
                    
                if key in KEY_BINDINGS:
                    twist_msg.linear.x = KEY_BINDINGS[key][0]
                    twist_msg.angular.z = KEY_BINDINGS[key][1]
                    self.publisher.publish(twist_msg)
                    # Use \r to overwrite the line in the terminal smoothly
                    print(f"\rPublished: v={twist_msg.linear.x} m/s, w={twist_msg.angular.z} rad/s   ", end='')

        except Exception as e:
            self.get_logger().error(f"Error reading keyboard: {e}")
        finally:
            # Publish a stop command before shutting down
            twist_msg.linear.x = 0.0
            twist_msg.angular.z = 0.0
            self.publisher.publish(twist_msg)
            print("\rStopping robot...")

def main(args=None):
    rclpy.init(args=args)
    node = KeyboardTeleopNode()
    node.run()
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
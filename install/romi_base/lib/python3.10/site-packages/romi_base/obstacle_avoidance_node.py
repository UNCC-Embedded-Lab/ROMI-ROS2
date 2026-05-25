import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan

class ObstacleAvoidanceNode(Node):
    def __init__(self):
        super().__init__('obstacle_avoidance_node')
        
        # Setup publisher for motion commands and subscriber for lidar scans.
        self.publisher = self.create_publisher(Twist, '/cmd_vel', 10)
        self.subscription = self.create_subscription(LaserScan, '/scan', self.lidar_callback, 10)
        
        # Configurable Parameters (Standard Roomba behavior)
        self.declare_parameter('forward_speed', 0.20)  # m/s
        self.declare_parameter('turning_speed', 1.0)   # rad/s
        self.declare_parameter('safe_dist', 0.5)       # meters (stop distance)
        
        self.get_logger().info("Obstacle Avoidance Node Initialized. Looking for obstacles...")

    def lidar_callback(self, msg):
        """
        Main logic: Slices the lidar array to find the 'Front' of the robot.
        """
        # RPLidar A1 typically has 360 points. 
        # Front is usually the beginning and end of the array.
        # Take 20 degrees on both sides of 0.
        front_left = msg.ranges[0:20]
        front_right = msg.ranges[340:360]
        
        # Combine and filter out 0.0 or 'inf' values (common lidar noise)
        front_arc = [r for r in (list(front_left) + list(front_right)) if r > 0.05]
        
        if not front_arc:
            return # No valid data yet
            
        min_dist = min(front_arc)
        
        # Create the Twist motion command.
        move_cmd = Twist()
        
        safe_threshold = self.get_parameter('safe_dist').value
        
        if min_dist < safe_threshold:
            # REACTION: Obstacle detected! Stop and Spin.
            move_cmd.linear.x = 0.0
            move_cmd.angular.z = self.get_parameter('turning_speed').value
            self.get_logger().info(f"OBSTACLE! Dist: {min_dist:.2f}m. Turning...")
        else:
            # DEFAULT: Path is clear. Drive forward.
            move_cmd.linear.x = self.get_parameter('forward_speed').value
            move_cmd.angular.z = 0.0

        self.publisher.publish(move_cmd)

def main(args=None):
    rclpy.init(args=args)
    node = ObstacleAvoidanceNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        # Emergency Stop on exit
        stop_cmd = Twist()
        node.publisher.publish(stop_cmd)
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
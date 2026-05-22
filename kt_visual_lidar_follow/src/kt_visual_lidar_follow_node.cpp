#include "kt_visual_lidar_follow/follow_types.hpp"
#include "kt_visual_lidar_follow/target_parser.hpp"
#include "kt_visual_lidar_follow/lidar_associator.hpp"
#include "kt_visual_lidar_follow/follow_fsm.hpp"

#include "rclcpp/rclcpp.hpp"
#include "std_msgs/msg/string.hpp"
#include "geometry_msgs/msg/twist_stamped.hpp"
#include "sensor_msgs/msg/camera_info.hpp"
#include "sensor_msgs/msg/laser_scan.hpp"
#include "ai_msgs/msg/perception_targets.hpp"

#include <cmath>
#include <memory>
#include <sstream>
#include <string>

namespace kt_visual_lidar_follow {

class KtVisualLidarFollowNode : public rclcpp::Node {
 public:
  explicit KtVisualLidarFollowNode(const rclcpp::NodeOptions &options)
  : Node("kt_visual_lidar_follow_node", options) {
    // Declare parameters
    dry_run_ = declare_parameter<bool>("dry_run", true);

    auto visual_topic  = declare_parameter<std::string>(
      "visual_targets_topic", "/bear_detection/targets");
    auto scan_topic    = declare_parameter<std::string>(
      "scan_topic", "/tianracer/scan");
    auto cam_info_topic = declare_parameter<std::string>(
      "camera_info_topic", "/tianracer/camera/camera_info");
    /* cmd_vel_topic is declared but never used as a publisher in dry-run */
    declare_parameter<std::string>("cmd_vel_topic", "/tianracer/cmd_vel");

    auto state_topic   = declare_parameter<std::string>(
      "state_topic", "/kt_follow/state");
    auto dbg_target_topic = declare_parameter<std::string>(
      "debug_target_topic", "/kt_follow/debug_target");
    auto dbg_cmd_topic = declare_parameter<std::string>(
      "debug_cmd_topic", "/kt_follow/debug_cmd");

    // FsmConfig
    FsmConfig fsm_cfg;
    fsm_cfg.desired_distance_m    = declare_parameter<double>("desired_distance_m", 1.2);
    fsm_cfg.min_safe_distance_m   = declare_parameter<double>("min_safe_distance_m", 0.6);
    fsm_cfg.max_follow_distance_m = declare_parameter<double>("max_follow_distance_m", 3.0);
    fsm_cfg.angle_window_deg      = declare_parameter<double>("angle_window_deg", 8.0);
    fsm_cfg.max_target_jump_deg   = declare_parameter<double>("max_target_jump_deg", 20.0);
    fsm_cfg.visual_timeout_ms     = declare_parameter<int>("visual_timeout_ms", 500);
    fsm_cfg.lidar_timeout_ms      = declare_parameter<int>("lidar_timeout_ms", 300);
    fsm_cfg.lidar_hold_timeout_ms = declare_parameter<int>("lidar_hold_timeout_ms", 800);
    fsm_cfg.linear_kp             = declare_parameter<double>("linear_kp", 0.3);
    fsm_cfg.angular_kp            = declare_parameter<double>("angular_kp", 0.8);
    fsm_cfg.max_linear_debug      = declare_parameter<double>("max_linear_debug", 0.15);
    fsm_cfg.max_angular_debug     = declare_parameter<double>("max_angular_debug", 0.4);

    // Target parser config
    target_parser_.set_target_type(
      declare_parameter<std::string>("target_type", "bear"));
    target_parser_.set_min_confidence(
      declare_parameter<double>("min_confidence", 0.5));

    // Lidar associator config
    lidar_associator_.set_angle_window_deg(
      declare_parameter<double>("angle_window_deg", 8.0));

    // FSM config
    fsm_.configure(fsm_cfg);

    // Publishers (dry-run: no cmd_vel publisher created)
    state_pub_ = create_publisher<std_msgs::msg::String>(state_topic, 10);
    dbg_target_pub_ = create_publisher<std_msgs::msg::String>(dbg_target_topic, 10);
    dbg_cmd_pub_ = create_publisher<geometry_msgs::msg::TwistStamped>(dbg_cmd_topic, 10);

    // Subscribers
    visual_sub_ = create_subscription<ai_msgs::msg::PerceptionTargets>(
      visual_topic, rclcpp::SensorDataQoS().keep_last(1),
      std::bind(&KtVisualLidarFollowNode::on_visual, this, std::placeholders::_1));

    scan_sub_ = create_subscription<sensor_msgs::msg::LaserScan>(
      scan_topic, rclcpp::SensorDataQoS().keep_last(1),
      std::bind(&KtVisualLidarFollowNode::on_scan, this, std::placeholders::_1));

    cam_info_sub_ = create_subscription<sensor_msgs::msg::CameraInfo>(
      cam_info_topic, rclcpp::SensorDataQoS().keep_last(1),
      std::bind(&KtVisualLidarFollowNode::on_camera_info, this, std::placeholders::_1));

    RCLCPP_INFO(get_logger(),
      "kt_visual_lidar_follow_node started (dry_run=%s)", dry_run_ ? "true" : "false");
    RCLCPP_INFO(get_logger(),
      "  visual_targets_topic: %s", visual_topic.c_str());
    RCLCPP_INFO(get_logger(),
      "  scan_topic: %s", scan_topic.c_str());
    RCLCPP_INFO(get_logger(),
      "  camera_info_topic: %s", cam_info_topic.c_str());
  }

 private:
  void on_camera_info(const sensor_msgs::msg::CameraInfo::ConstSharedPtr &msg) {
    fx_ = msg->k[0];
    cx_ = msg->k[2];
    has_camera_info_ = true;
    last_cam_info_stamp_ = static_cast<double>(msg->header.stamp.sec) +
                           static_cast<double>(msg->header.stamp.nanosec) * 1e-9;
  }

  void on_visual(const ai_msgs::msg::PerceptionTargets::ConstSharedPtr &msg) {
    latest_visual_ = target_parser_.parse(msg);
    last_visual_stamp_ = now().seconds();
    run_fsm();
  }

  void on_scan(const sensor_msgs::msg::LaserScan::ConstSharedPtr &msg) {
    latest_scan_ = msg;
    last_scan_stamp_ = now().seconds();
    run_fsm();
  }

  void run_fsm() {
    const double current_time = now().seconds();

    // Compute theta from visual target if we have camera info
    double theta_rad = 0.0;
    bool visual_valid = latest_visual_.valid && has_camera_info_;

    if (visual_valid && fx_ > 0.0) {
      theta_rad = std::atan2(latest_visual_.center_x - cx_, fx_);
    }

    // Associate lidar
    LidarResult lidar_result;
    double lidar_stamp = 0.0;
    if (latest_scan_ && visual_valid) {
      lidar_result = lidar_associator_.associate(latest_scan_, theta_rad);
      lidar_stamp = static_cast<double>(latest_scan_->header.stamp.sec) +
                    static_cast<double>(latest_scan_->header.stamp.nanosec) * 1e-9;
    }

    // Check scan timeout
    bool scan_timeout = false;
    if (last_scan_stamp_ > 0.0) {
      double scan_age_ms = (current_time - last_scan_stamp_) * 1000.0;
      scan_timeout = scan_age_ms > 500.0;  // 500ms scan timeout
    }

    // Build FSM input
    FollowFsm::Input fsm_in;
    fsm_in.visual_valid      = visual_valid;
    fsm_in.visual_theta_rad  = theta_rad;
    fsm_in.visual_stamp_sec  = latest_visual_.stamp_sec;
    fsm_in.visual_confidence = latest_visual_.confidence;
    fsm_in.lidar_associated  = lidar_result.associated;
    fsm_in.lidar_distance_m  = lidar_result.distance_m;
    fsm_in.lidar_stamp_sec   = lidar_stamp;
    fsm_in.lidar_valid_count = lidar_result.valid_count;
    fsm_in.camera_info_ok    = has_camera_info_;
    fsm_in.scan_timeout      = scan_timeout;
    fsm_in.current_time_sec  = current_time;

    auto out = fsm_.update(fsm_in);

    // Publish state
    {
      auto msg = std::make_unique<std_msgs::msg::String>();
      std::ostringstream oss;
      oss << StateToString(out.state);
      if (out.stop_reason) {
        oss << " reason=" << out.stop_reason;
      }
      msg->data = oss.str();
      state_pub_->publish(std::move(msg));
    }

    // Publish debug target
    {
      auto msg = std::make_unique<std_msgs::msg::String>();
      std::ostringstream oss;
      oss.setf(std::ios::fixed);
      oss.precision(3);
      if (latest_visual_.valid) {
        oss << "cx=" << latest_visual_.center_x
            << " cy=" << latest_visual_.center_y
            << " w=" << latest_visual_.width
            << " h=" << latest_visual_.height
            << " conf=" << latest_visual_.confidence
            << " theta=" << theta_rad;
      } else {
        oss << "no_target";
      }
      if (lidar_result.associated) {
        oss << " dist=" << lidar_result.distance_m
            << " valid_pts=" << lidar_result.valid_count;
      }
      msg->data = oss.str();
      dbg_target_pub_->publish(std::move(msg));
    }

    // Publish debug cmd (suggested velocity, never goes to chassis)
    {
      auto msg = std::make_unique<geometry_msgs::msg::TwistStamped>();
      msg->header.stamp = now();
      msg->twist.linear.x  = out.cmd.linear_x;
      msg->twist.angular.z = out.cmd.angular_z;
      dbg_cmd_pub_->publish(std::move(msg));
    }
  }

  // State
  bool dry_run_ = true;
  bool has_camera_info_ = false;
  double fx_ = 0.0;
  double cx_ = 0.0;
  double last_cam_info_stamp_ = 0.0;
  double last_visual_stamp_ = 0.0;
  double last_scan_stamp_ = 0.0;

  VisualTarget latest_visual_;
  sensor_msgs::msg::LaserScan::ConstSharedPtr latest_scan_;

  TargetParser target_parser_;
  LidarAssociator lidar_associator_;
  FollowFsm fsm_;

  // Publishers
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr state_pub_;
  rclcpp::Publisher<std_msgs::msg::String>::SharedPtr dbg_target_pub_;
  rclcpp::Publisher<geometry_msgs::msg::TwistStamped>::SharedPtr dbg_cmd_pub_;

  // Subscribers
  rclcpp::Subscription<ai_msgs::msg::PerceptionTargets>::SharedPtr visual_sub_;
  rclcpp::Subscription<sensor_msgs::msg::LaserScan>::SharedPtr scan_sub_;
  rclcpp::Subscription<sensor_msgs::msg::CameraInfo>::SharedPtr cam_info_sub_;
};

}  // namespace kt_visual_lidar_follow

int main(int argc, char **argv) {
  rclcpp::init(argc, argv);
  auto node = std::make_shared<kt_visual_lidar_follow::KtVisualLidarFollowNode>(
    rclcpp::NodeOptions());
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}

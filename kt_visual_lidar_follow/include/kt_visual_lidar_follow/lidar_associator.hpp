#ifndef KT_VISUAL_LIDAR_FOLLOW__LIDAR_ASSOCIATOR_HPP_
#define KT_VISUAL_LIDAR_FOLLOW__LIDAR_ASSOCIATOR_HPP_

#include "kt_visual_lidar_follow/follow_types.hpp"

#include "sensor_msgs/msg/laser_scan.hpp"

namespace kt_visual_lidar_follow {

class LidarAssociator {
 public:
  void set_angle_window_deg(double deg);

  LidarResult associate(
    const sensor_msgs::msg::LaserScan::ConstSharedPtr &scan,
    double target_theta_rad) const;

 private:
  double angle_window_deg_ = 8.0;
};

}  // namespace kt_visual_lidar_follow

#endif  // KT_VISUAL_LIDAR_FOLLOW__LIDAR_ASSOCIATOR_HPP_

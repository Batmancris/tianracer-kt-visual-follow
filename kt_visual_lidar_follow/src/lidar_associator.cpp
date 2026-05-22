#include "kt_visual_lidar_follow/lidar_associator.hpp"

#include <algorithm>
#include <cmath>
#include <vector>

namespace kt_visual_lidar_follow {

void LidarAssociator::set_angle_window_deg(double deg) {
  angle_window_deg_ = deg;
}

LidarResult LidarAssociator::associate(
  const sensor_msgs::msg::LaserScan::ConstSharedPtr &scan,
  double target_theta_rad) const
{
  LidarResult result;

  if (!scan || scan->ranges.empty()) {
    return result;
  }

  const double window_rad = angle_window_deg_ * M_PI / 180.0;
  const double theta_min = target_theta_rad - window_rad;
  const double theta_max = target_theta_rad + window_rad;

  const int n = static_cast<int>(scan->ranges.size());
  const double angle_min = scan->angle_min;
  const double angle_inc = scan->angle_increment;

  if (angle_inc <= 0.0 || n <= 0) {
    return result;
  }

  const int idx_min = std::max(0,
    static_cast<int>(std::floor((theta_min - angle_min) / angle_inc)));
  const int idx_max = std::min(n - 1,
    static_cast<int>(std::ceil((theta_max - angle_min) / angle_inc)));

  std::vector<double> valid_ranges;
  valid_ranges.reserve(static_cast<size_t>(std::max(0, idx_max - idx_min + 1)));

  for (int i = idx_min; i <= idx_max; ++i) {
    if (i < 0 || i >= n) {
      continue;
    }
    float r = scan->ranges[i];
    if (std::isnan(r) || std::isinf(r)) {
      continue;
    }
    if (r < scan->range_min || r > scan->range_max) {
      continue;
    }
    valid_ranges.push_back(static_cast<double>(r));
  }

  if (valid_ranges.empty()) {
    return result;
  }

  std::sort(valid_ranges.begin(), valid_ranges.end());
  size_t mid = valid_ranges.size() / 2;
  double median = (valid_ranges.size() % 2 == 0)
    ? (valid_ranges[mid - 1] + valid_ranges[mid]) * 0.5
    : valid_ranges[mid];

  result.associated   = true;
  result.distance_m   = median;
  result.valid_count  = static_cast<int>(valid_ranges.size());
  result.angle_min_used = angle_min + static_cast<double>(idx_min) * angle_inc;
  result.angle_max_used = angle_min + static_cast<double>(idx_max) * angle_inc;

  return result;
}

}  // namespace kt_visual_lidar_follow

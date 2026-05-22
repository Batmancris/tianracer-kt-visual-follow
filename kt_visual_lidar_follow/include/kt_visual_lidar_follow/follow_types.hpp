#ifndef KT_VISUAL_LIDAR_FOLLOW__FOLLOW_TYPES_HPP_
#define KT_VISUAL_LIDAR_FOLLOW__FOLLOW_TYPES_HPP_

#include <cstdint>
#include <string>

namespace kt_visual_lidar_follow {

enum class FollowState : uint8_t {
  IDLE = 0,
  VISION_LOCK,
  VISION_LIDAR_FUSED,
  LIDAR_HOLD,
  SEARCH,
  STOP
};

inline const char * StateToString(FollowState s) {
  switch (s) {
    case FollowState::IDLE:               return "IDLE";
    case FollowState::VISION_LOCK:        return "VISION_LOCK";
    case FollowState::VISION_LIDAR_FUSED: return "VISION_LIDAR_FUSED";
    case FollowState::LIDAR_HOLD:         return "LIDAR_HOLD";
    case FollowState::SEARCH:             return "SEARCH";
    case FollowState::STOP:               return "STOP";
    default:                              return "UNKNOWN";
  }
}

struct VisualTarget {
  double center_x = 0.0;
  double center_y = 0.0;
  double width    = 0.0;
  double height   = 0.0;
  double confidence = 0.0;
  double stamp_sec = 0.0;
  bool   valid    = false;
};

struct LidarResult {
  bool   associated   = false;
  double distance_m   = 0.0;
  int    valid_count  = 0;
  double angle_min_used = 0.0;
  double angle_max_used = 0.0;
};

struct FollowCmd {
  double linear_x  = 0.0;
  double angular_z = 0.0;
};

}  // namespace kt_visual_lidar_follow

#endif  // KT_VISUAL_LIDAR_FOLLOW__FOLLOW_TYPES_HPP_

#ifndef KT_VISUAL_LIDAR_FOLLOW__TARGET_PARSER_HPP_
#define KT_VISUAL_LIDAR_FOLLOW__TARGET_PARSER_HPP_

#include "kt_visual_lidar_follow/follow_types.hpp"

#include "ai_msgs/msg/perception_targets.hpp"

#include <string>

namespace kt_visual_lidar_follow {

class TargetParser {
 public:
  void set_target_type(const std::string &type);
  void set_min_confidence(double conf);

  VisualTarget parse(const ai_msgs::msg::PerceptionTargets::ConstSharedPtr &msg) const;

 private:
  std::string target_type_ = "bear";
  double min_confidence_ = 0.5;
};

}  // namespace kt_visual_lidar_follow

#endif  // KT_VISUAL_LIDAR_FOLLOW__TARGET_PARSER_HPP_

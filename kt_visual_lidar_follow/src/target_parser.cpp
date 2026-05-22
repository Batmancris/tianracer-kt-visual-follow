#include "kt_visual_lidar_follow/target_parser.hpp"

#include <algorithm>
#include <string>

namespace kt_visual_lidar_follow {

void TargetParser::set_target_type(const std::string &type) {
  target_type_ = type;
}

void TargetParser::set_min_confidence(double conf) {
  min_confidence_ = conf;
}

VisualTarget TargetParser::parse(
  const ai_msgs::msg::PerceptionTargets::ConstSharedPtr &msg) const
{
  VisualTarget result;

  if (!msg || msg->targets.empty()) {
    return result;
  }

  double best_area = 0.0;

  for (const auto &target : msg->targets) {
    for (const auto &roi : target.rois) {
      if (roi.type != target_type_) {
        continue;
      }
      if (roi.confidence < min_confidence_) {
        continue;
      }

      double area = static_cast<double>(roi.rect.width) *
                    static_cast<double>(roi.rect.height);
      if (area > best_area) {
        best_area = area;
        result.center_x = static_cast<double>(roi.rect.x_offset) +
                          static_cast<double>(roi.rect.width) * 0.5;
        result.center_y = static_cast<double>(roi.rect.y_offset) +
                          static_cast<double>(roi.rect.height) * 0.5;
        result.width    = static_cast<double>(roi.rect.width);
        result.height   = static_cast<double>(roi.rect.height);
        result.confidence = roi.confidence;
        result.valid    = true;
      }
    }
  }

  if (result.valid) {
    result.stamp_sec = static_cast<double>(msg->header.stamp.sec) +
                       static_cast<double>(msg->header.stamp.nanosec) * 1e-9;
  }

  return result;
}

}  // namespace kt_visual_lidar_follow

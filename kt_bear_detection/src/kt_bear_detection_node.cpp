// kt_bear_detection_node.cpp
// Adapted from rm_bear_detection/src/bear_detection_node.cpp
// Key differences from rm_bear_detection:
//   - Input: sensor_msgs/msg/Image (via cv_bridge) instead of hbm_img_msgs/HbmMsg1080P
//   - BGR->NV12 conversion via OpenCV (no hobot_cv resize on NV12 path)
//   - No gimbal / motor control logic
//   - Namespace: kt_bear_detection

#include "ai_msgs/msg/perception_targets.hpp"
#include "ament_index_cpp/get_package_prefix.hpp"
#include "cv_bridge/cv_bridge.h"
#include "dnn_node/dnn_node.h"
#include "dnn_node/util/image_proc.h"
#include "hobot_cv/hobotcv_imgproc.h"
#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/image.hpp"
#include "std_msgs/msg/header.hpp"
#include "std_msgs/msg/string.hpp"

#include "kt_bear_detection/parser.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <memory>
#include <mutex>
#include <opencv2/opencv.hpp>
#include <sstream>
#include <string>
#include <vector>

namespace {

std::string GetDefaultModelPath() {
  const auto package_prefix = ament_index_cpp::get_package_prefix("kt_bear_detection");
  return package_prefix + "/lib/kt_bear_detection/config/bear_yolov8n_x5_640_nv12.bin";
}

kt_bear_detection::YoloBoxFormat ParseBoxFormat(const std::string &value) {
  if (value == "cxcywh") {
    return kt_bear_detection::YoloBoxFormat::kCxcywh;
  }
  return kt_bear_detection::YoloBoxFormat::kXyxy;
}

// Convert BGR image to NV12 format in-place into a pre-allocated buffer.
// NV12 layout: Y plane (height * width) followed by interleaved UV plane (height/2 * width).
void BgrToNv12(const cv::Mat &bgr, uint8_t *nv12_data) {
  const int width = bgr.cols;
  const int height = bgr.rows;
  cv::Mat yuv;
  cv::cvtColor(bgr, yuv, cv::COLOR_BGR2YUV_I420);

  const uint8_t *yuv_data = yuv.data;
  // Y plane
  std::memcpy(nv12_data, yuv_data, static_cast<std::size_t>(width * height));

  // UV plane: I420 has planar U then V; NV12 has interleaved UV.
  const uint8_t *u_plane = yuv_data + width * height;
  const uint8_t *v_plane = u_plane + (width / 2) * (height / 2);
  uint8_t *uv_dst = nv12_data + width * height;
  const int uv_size = (width / 2) * (height / 2);
  for (int i = 0; i < uv_size; ++i) {
    uv_dst[2 * i] = u_plane[i];
    uv_dst[2 * i + 1] = v_plane[i];
  }
}

// Letterbox a BGR image to target size, return the letterboxed NV12 pyramid input.
// Fills scale/pad info for coordinate remapping.
std::shared_ptr<hobot::dnn_node::NV12PyramidInput> LetterboxBgrToNv12Pyramid(
  const cv::Mat &bgr,
  int target_w,
  int target_h,
  float &scale_to_original,
  float &pad_x,
  float &pad_y) {
  const int src_w = bgr.cols;
  const int src_h = bgr.rows;

  const float ratio_w = static_cast<float>(src_w) / static_cast<float>(target_w);
  const float ratio_h = static_cast<float>(src_h) / static_cast<float>(target_h);
  const float ratio = std::max(ratio_w, ratio_h);

  int resized_w = static_cast<int>(static_cast<float>(src_w) / ratio);
  int resized_h = static_cast<int>(static_cast<float>(src_h) /ratio);

  // Round down to even (NV12 requires even dimensions)
  resized_w = resized_w - (resized_w % 2);
  resized_h = resized_h - (resized_h % 2);

  cv::Mat resized;
  cv::resize(bgr, resized, cv::Size(resized_w, resized_h));

  // Create letterboxed image: target_h x target_w, filled with gray (114)
  cv::Mat letterboxed(target_h, target_w, CV_8UC3, cv::Scalar(114, 114, 114));

  const int left = (target_w - resized_w) / 2;
  const int top = (target_h - resized_h) / 2;
  resized.copyTo(letterboxed(cv::Rect(left, top, resized_w, resized_h)));

  // Convert BGR letterboxed image to NV12
  const int nv12_size = target_w * target_h * 3 / 2;
  auto nv12_buf = std::make_unique<uint8_t[]>(static_cast<std::size_t>(nv12_size));
  BgrToNv12(letterboxed, nv12_buf.get());

  // Build NV12 pyramid input for DNN
  auto pyramid = hobot::dnn_node::ImageProc::GetNV12PyramidFromNV12Img(
    reinterpret_cast<const char *>(nv12_buf.get()),
    static_cast<uint32_t>(target_h),
    static_cast<uint32_t>(target_w),
    target_h,
    target_w);

  scale_to_original = ratio;
  pad_x = static_cast<float>(left);
  pad_y = static_cast<float>(top);
  return pyramid;
}

struct BearNodeOutput : public hobot::dnn_node::DnnNodeOutput {
  float scale_to_original = 1.0F;
  float pad_x = 0.0F;
  float pad_y = 0.0F;
  int original_width = 0;
  int original_height = 0;
};

struct PublishCandidate {
  ai_msgs::msg::Target target;
  double center_x = 0.0;
  double center_y = 0.0;
};

struct StableTrack {
  std::string type;
  double center_x = 0.0;
  double center_y = 0.0;
  int hits = 0;
  rclcpp::Time stamp{0, 0, RCL_ROS_TIME};
};

}  // namespace

class KtBearDetectionNode : public hobot::dnn_node::DnnNode {
 public:
  explicit KtBearDetectionNode(
    const std::string &node_name = "kt_bear_detection",
    const rclcpp::NodeOptions &options = rclcpp::NodeOptions())
  : hobot::dnn_node::DnnNode(node_name, options) {
    image_topic_ = this->declare_parameter<std::string>(
      "image_topic", "/tianracer/camera/image_raw");
    output_topic_ = this->declare_parameter<std::string>(
      "output_topic", "/bear_detection/targets");
    target_type_ = this->declare_parameter<std::string>("target_type", "bear");
    model_path_ = this->declare_parameter<std::string>("model_path", GetDefaultModelPath());
    box_format_name_ = this->declare_parameter<std::string>("box_format", "cxcywh");
    if (box_format_name_ != "xyxy" && box_format_name_ != "cxcywh") {
      RCLCPP_WARN(
        this->get_logger(),
        "Unsupported box_format '%s', falling back to 'xyxy'",
        box_format_name_.c_str());
      box_format_name_ = "xyxy";
    }
    box_format_ = ParseBoxFormat(box_format_name_);
    score_threshold_ = this->declare_parameter<double>("score_threshold", 0.71);
    nms_threshold_ = this->declare_parameter<double>("nms_threshold", 0.70);
    nms_top_k_ = this->declare_parameter<int>("nms_top_k", 300);
    stable_required_hits_ = this->declare_parameter<int>("stable_required_hits", 2);
    stable_match_radius_px_ = this->declare_parameter<double>("stable_match_radius_px", 140.0);
    stable_max_track_age_ms_ = this->declare_parameter<int>("stable_max_track_age_ms", 200);
    task_num_ = this->declare_parameter<int>("task_num", 4);
    log_fps_ = this->declare_parameter<bool>("log_fps", false);
    log_detections_ = this->declare_parameter<bool>("log_detections", false);
    publish_debug_log_ = this->declare_parameter<bool>("publish_debug_log", true);
    debug_raw_candidates_ = this->declare_parameter<bool>("debug_raw_candidates", false);

    if (Init() != 0 || GetModelInputSize(0, model_input_width_, model_input_height_) < 0) {
      RCLCPP_ERROR(this->get_logger(), "Failed to initialize kt_bear_detection");
      rclcpp::shutdown();
      return;
    }

    RCLCPP_INFO(
      this->get_logger(),
      "kt_bear_detection model input: %dx%d",
      model_input_width_, model_input_height_);

    auto sub_qos = rclcpp::SensorDataQoS().keep_last(1);
    image_subscription_ = this->create_subscription<sensor_msgs::msg::Image>(
      image_topic_,
      sub_qos,
      std::bind(&KtBearDetectionNode::OnImage, this, std::placeholders::_1));

    auto pub_qos = rclcpp::SensorDataQoS().keep_last(1);
    publisher_ = this->create_publisher<ai_msgs::msg::PerceptionTargets>(output_topic_, pub_qos);
  }

 protected:
  int SetNodePara() override {
    if (!dnn_node_para_ptr_) {
      return -1;
    }

    if (model_path_.empty()) {
      RCLCPP_ERROR(
        this->get_logger(),
        "Parameter 'model_path' is empty. Please set it to a valid quant.bin path");
      return -1;
    }

    dnn_node_para_ptr_->model_file = model_path_;
    dnn_node_para_ptr_->model_task_type = hobot::dnn_node::ModelTaskType::ModelInferType;
    dnn_node_para_ptr_->task_num = task_num_;
    return 0;
  }

  int PostProcess(
    const std::shared_ptr<hobot::dnn_node::DnnNodeOutput> &node_output) override {
    if (!rclcpp::ok() || !node_output) {
      return 0;
    }

    auto pub_msg = std::make_unique<ai_msgs::msg::PerceptionTargets>();
    pub_msg->header = *node_output->msg_header;

    std::vector<std::shared_ptr<kt_bear_detection::YoloV8Detection>> detections;
    const kt_bear_detection::YoloV8ParserConfig parser_config {
      static_cast<float>(score_threshold_),
      static_cast<float>(nms_threshold_),
      nms_top_k_,
      target_type_,
      model_input_width_,
      model_input_height_,
      box_format_,
      debug_raw_candidates_,
    };

    if (kt_bear_detection::ParseDetections(node_output, parser_config, detections) != 0) {
      RCLCPP_ERROR_THROTTLE(
        this->get_logger(), *this->get_clock(), 2000, "Failed to parse bear detections");
      return -1;
    }

    auto bear_output = std::dynamic_pointer_cast<BearNodeOutput>(node_output);
    if (!bear_output) {
      RCLCPP_ERROR(this->get_logger(), "Failed to cast bear node output");
      return -1;
    }

    std::vector<PublishCandidate> candidates;
    candidates.reserve(detections.size());
    for (auto &det : detections) {
      if (!det) {
        continue;
      }

      // Map from model coordinates back to original image coordinates
      const float xmin =
        std::clamp((det->xmin - bear_output->pad_x) * bear_output->scale_to_original,
          0.0F, static_cast<float>(bear_output->original_width - 1));
      const float ymin =
        std::clamp((det->ymin - bear_output->pad_y) * bear_output->scale_to_original,
          0.0F, static_cast<float>(bear_output->original_height - 1));
      const float xmax =
        std::clamp((det->xmax - bear_output->pad_x) * bear_output->scale_to_original,
          0.0F, static_cast<float>(bear_output->original_width - 1));
      const float ymax =
        std::clamp((det->ymax - bear_output->pad_y) * bear_output->scale_to_original,
          0.0F, static_cast<float>(bear_output->original_height - 1));

      if (xmax <= xmin || ymax <= ymin) {
        continue;
      }

      ai_msgs::msg::Roi roi;
      roi.rect.x_offset = static_cast<uint32_t>(std::lround(xmin));
      roi.rect.y_offset = static_cast<uint32_t>(std::lround(ymin));
      roi.rect.width = static_cast<uint32_t>(std::lround(xmax - xmin));
      roi.rect.height = static_cast<uint32_t>(std::lround(ymax - ymin));
      roi.confidence = det->score;

      ai_msgs::msg::Target target;
      target.type = det->class_name;
      target.rois.emplace_back(std::move(roi));
      candidates.push_back(PublishCandidate {
        std::move(target),
        (xmin + xmax) * 0.5,
        (ymin + ymax) * 0.5,
      });
    }

    ApplyStableTargetFilter(candidates, *pub_msg);

    if (publish_debug_log_ && !pub_msg->targets.empty() && !pub_msg->targets.front().rois.empty()) {
      const auto &rect = pub_msg->targets.front().rois.front().rect;
      RCLCPP_INFO_THROTTLE(
        this->get_logger(), *this->get_clock(), 1000,
        "bear roi x=%u y=%u w=%u h=%u conf=%.2f targets=%zu",
        rect.x_offset, rect.y_offset, rect.width, rect.height,
        pub_msg->targets.front().rois.front().confidence,
        pub_msg->targets.size());
    }

    if (node_output->rt_stat) {
      pub_msg->fps = std::lround(node_output->rt_stat->output_fps);
      if (log_fps_ && node_output->rt_stat->fps_updated) {
        RCLCPP_INFO_THROTTLE(
          this->get_logger(), *this->get_clock(), 2000,
          "bear detection fps in=%.2f out=%.2f infer=%dms targets=%zu",
          node_output->rt_stat->input_fps,
          node_output->rt_stat->output_fps,
          node_output->rt_stat->infer_time_ms,
          pub_msg->targets.size());
      }
    }

    publisher_->publish(std::move(pub_msg));
    return 0;
  }

 private:
  void OnImage(const sensor_msgs::msg::Image::ConstSharedPtr &msg) {
    if (!rclcpp::ok() || !msg) {
      return;
    }

    cv_bridge::CvImageConstPtr cv_ptr;
    try {
      cv_ptr = cv_bridge::toCvShare(msg, "bgr8");
    } catch (const cv_bridge::Exception &e) {
      RCLCPP_ERROR_THROTTLE(
        this->get_logger(), *this->get_clock(), 2000,
        "cv_bridge conversion failed: %s", e.what());
      return;
    }

    auto output = std::make_shared<BearNodeOutput>();
    output->msg_header = std::make_shared<std_msgs::msg::Header>();
    output->msg_header->frame_id = msg->header.frame_id;
    output->msg_header->stamp = msg->header.stamp;
    output->original_width = cv_ptr->image.cols;
    output->original_height = cv_ptr->image.rows;

    auto pyramid = LetterboxBgrToNv12Pyramid(
      cv_ptr->image,
      model_input_width_,
      model_input_height_,
      output->scale_to_original,
      output->pad_x,
      output->pad_y);

    if (!pyramid) {
      RCLCPP_ERROR(this->get_logger(), "Failed to create NV12 pyramid input");
      return;
    }

    std::vector<std::shared_ptr<hobot::dnn_node::DNNInput>> inputs {pyramid};
    if (Run(inputs, output, nullptr, false) < 0) {
      RCLCPP_ERROR_THROTTLE(
        this->get_logger(), *this->get_clock(), 1000, "Bear inference run failed");
    }
  }

  void ApplyStableTargetFilter(
    const std::vector<PublishCandidate> &candidates,
    ai_msgs::msg::PerceptionTargets &pub_msg) {
    if (stable_required_hits_ <= 1) {
      for (const auto &candidate : candidates) {
        pub_msg.targets.emplace_back(candidate.target);
      }
      return;
    }

    const auto stamp = now();
    std::vector<StableTrack> next_tracks;
    next_tracks.reserve(candidates.size());

    std::lock_guard<std::mutex> lock(stable_tracks_mutex_);
    PruneExpiredStableTracks(stamp);

    for (const auto &candidate : candidates) {
      const auto matched_index = FindMatchingStableTrack(candidate);
      int hits = 1;
      if (matched_index >= 0) {
        hits = std::min(
          stable_required_hits_,
          stable_tracks_[static_cast<std::size_t>(matched_index)].hits + 1);
      }

      next_tracks.push_back(StableTrack {
        candidate.target.type,
        candidate.center_x,
        candidate.center_y,
        hits,
        stamp,
      });

      if (hits >= stable_required_hits_) {
        pub_msg.targets.emplace_back(candidate.target);
      }
    }

    stable_tracks_ = std::move(next_tracks);
  }

  void PruneExpiredStableTracks(const rclcpp::Time &stamp) {
    const auto max_age =
      rclcpp::Duration::from_seconds(static_cast<double>(stable_max_track_age_ms_) / 1000.0);
    stable_tracks_.erase(
      std::remove_if(
        stable_tracks_.begin(),
        stable_tracks_.end(),
        [&](const StableTrack &track) {
          return track.stamp.nanoseconds() <= 0 || (stamp - track.stamp) > max_age;
        }),
      stable_tracks_.end());
  }

  int FindMatchingStableTrack(const PublishCandidate &candidate) const {
    int best_index = -1;
    double best_distance = stable_match_radius_px_;
    for (std::size_t i = 0; i < stable_tracks_.size(); ++i) {
      const auto &track = stable_tracks_[i];
      if (track.type != candidate.target.type) {
        continue;
      }
      const double distance = std::hypot(
        candidate.center_x - track.center_x,
        candidate.center_y - track.center_y);
      if (distance <= best_distance) {
        best_distance = distance;
        best_index = static_cast<int>(i);
      }
    }
    return best_index;
  }

  std::string image_topic_;
  std::string output_topic_;
  std::string target_type_;
  std::string model_path_;
  std::string box_format_name_;
  double score_threshold_{0.71};
  double nms_threshold_{0.70};
  int nms_top_k_{300};
  int stable_required_hits_{2};
  double stable_match_radius_px_{140.0};
  int stable_max_track_age_ms_{200};
  int task_num_{4};
  bool log_fps_{false};
  bool log_detections_{false};
  bool publish_debug_log_{true};
  bool debug_raw_candidates_{false};
  kt_bear_detection::YoloBoxFormat box_format_{kt_bear_detection::YoloBoxFormat::kCxcywh};
  int model_input_width_{-1};
  int model_input_height_{-1};
  rclcpp::Subscription<sensor_msgs::msg::Image>::ConstSharedPtr image_subscription_;
  rclcpp::Publisher<ai_msgs::msg::PerceptionTargets>::SharedPtr publisher_;
  std::mutex stable_tracks_mutex_;
  std::vector<StableTrack> stable_tracks_;
};

int main(int argc, char **argv) {
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<KtBearDetectionNode>());
  rclcpp::shutdown();
  return 0;
}

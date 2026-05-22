#include "kt_visual_lidar_follow/follow_fsm.hpp"

#include <algorithm>
#include <cmath>
#include <cstring>

namespace kt_visual_lidar_follow {

void FollowFsm::configure(const FsmConfig &cfg) {
  cfg_ = cfg;
}

FollowFsm::Output FollowFsm::update(const Input &in) {
  Output out;

  // Check stop conditions first (highest priority)
  const char *stop_reason = nullptr;
  if (check_stop_conditions(in, stop_reason)) {
    transition_to(FollowState::STOP);
    out.state = state_;
    out.cmd = {0.0, 0.0};
    out.stop_reason = stop_reason;
    return out;
  }

  // Update tracking timestamps
  if (in.visual_valid) {
    last_visual_stamp_sec_ = in.visual_stamp_sec;
  }
  if (in.lidar_associated) {
    last_lidar_stamp_sec_ = in.lidar_stamp_sec;
    last_lidar_distance_m_ = in.lidar_distance_m;
    last_lidar_theta_rad_ = in.visual_theta_rad;
    has_last_lidar_ = true;
  }

  // State transitions
  switch (state_) {
    case FollowState::IDLE: {
      if (in.visual_valid && in.camera_info_ok) {
        transition_to(FollowState::VISION_LOCK);
      }
      out.cmd = {0.0, 0.0};
      break;
    }

    case FollowState::VISION_LOCK: {
      if (!in.visual_valid) {
        // Visual lost immediately -> SEARCH
        transition_to(FollowState::SEARCH);
        out.cmd = {0.0, 0.0};
      } else if (in.lidar_associated && in.lidar_valid_count > 0) {
        transition_to(FollowState::VISION_LIDAR_FUSED);
        double distance_error = in.lidar_distance_m - cfg_.desired_distance_m;
        out.cmd.linear_x  = std::clamp(
          cfg_.linear_kp * distance_error, -cfg_.max_linear_debug, cfg_.max_linear_debug);
        out.cmd.angular_z = std::clamp(
          -cfg_.angular_kp * in.visual_theta_rad, -cfg_.max_angular_debug, cfg_.max_angular_debug);
      } else {
        // Still waiting for lidar association
        out.cmd = {0.0, 0.0};
      }
      break;
    }

    case FollowState::VISION_LIDAR_FUSED: {
      if (!in.visual_valid) {
        transition_to(FollowState::LIDAR_HOLD);
        out.cmd = {0.0, 0.0};
      } else if (!in.lidar_associated || in.lidar_valid_count <= 0) {
        // Visual ok but lidar lost association
        transition_to(FollowState::VISION_LOCK);
        out.cmd = {0.0, 0.0};
      } else {
        double distance_error = in.lidar_distance_m - cfg_.desired_distance_m;
        out.cmd.linear_x  = std::clamp(
          cfg_.linear_kp * distance_error, -cfg_.max_linear_debug, cfg_.max_linear_debug);
        out.cmd.angular_z = std::clamp(
          -cfg_.angular_kp * in.visual_theta_rad, -cfg_.max_angular_debug, cfg_.max_angular_debug);
      }
      break;
    }

    case FollowState::LIDAR_HOLD: {
      double elapsed_ms = (in.current_time_sec - last_visual_stamp_sec_) * 1000.0;

      if (in.visual_valid) {
        // Visual recovered
        if (in.lidar_associated && in.lidar_valid_count > 0) {
          transition_to(FollowState::VISION_LIDAR_FUSED);
        } else {
          transition_to(FollowState::VISION_LOCK);
        }
        out.cmd = {0.0, 0.0};
      } else if (elapsed_ms > cfg_.lidar_hold_timeout_ms) {
        transition_to(FollowState::SEARCH);
        out.cmd = {0.0, 0.0};
      } else if (has_last_lidar_) {
        // Use last known lidar distance in the theta window
        double distance_error = last_lidar_distance_m_ - cfg_.desired_distance_m;
        out.cmd.linear_x  = std::clamp(
          cfg_.linear_kp * distance_error, -cfg_.max_linear_debug, cfg_.max_linear_debug);
        out.cmd.angular_z = std::clamp(
          -cfg_.angular_kp * last_lidar_theta_rad_, -cfg_.max_angular_debug, cfg_.max_angular_debug);
      } else {
        out.cmd = {0.0, 0.0};
      }
      break;
    }

    case FollowState::SEARCH: {
      if (in.visual_valid && in.camera_info_ok) {
        transition_to(FollowState::VISION_LOCK);
      }
      // First version: no active rotation search
      out.cmd = {0.0, 0.0};
      break;
    }

    case FollowState::STOP: {
      // Recovery: if all conditions clear, go to IDLE
      if (in.camera_info_ok && !in.scan_timeout) {
        transition_to(FollowState::IDLE);
      }
      out.cmd = {0.0, 0.0};
      break;
    }
  }

  out.state = state_;
  return out;
}

void FollowFsm::transition_to(FollowState new_state) {
  state_ = new_state;
  if (new_state == FollowState::IDLE) {
    has_prev_theta_ = false;
    has_last_lidar_ = false;
  }
}

bool FollowFsm::check_stop_conditions(const Input &in, const char *&reason) {
  if (!in.camera_info_ok) {
    reason = "camera_info_missing";
    return true;
  }
  if (in.scan_timeout) {
    reason = "scan_timeout";
    return true;
  }
  if (in.visual_valid && in.lidar_associated &&
      in.lidar_distance_m < cfg_.min_safe_distance_m &&
      in.lidar_distance_m > 0.0)
  {
    reason = "target_too_close";
    return true;
  }
  if (is_theta_jump(in)) {
    reason = "theta_jump";
    return true;
  }
  if (is_visual_timeout(in)) {
    reason = "visual_timeout";
    // Only force STOP from states that require visual
    if (state_ == FollowState::VISION_LOCK ||
        state_ == FollowState::VISION_LIDAR_FUSED) {
      return true;
    }
  }
  return false;
}

bool FollowFsm::is_visual_timeout(const Input &in) const {
  if (last_visual_stamp_sec_ <= 0.0) {
    return false;
  }
  double elapsed_ms = (in.current_time_sec - last_visual_stamp_sec_) * 1000.0;
  return elapsed_ms > cfg_.visual_timeout_ms;
}

bool FollowFsm::is_lidar_timeout(const Input &in) const {
  if (last_lidar_stamp_sec_ <= 0.0) {
    return false;
  }
  double elapsed_ms = (in.current_time_sec - last_lidar_stamp_sec_) * 1000.0;
  return elapsed_ms > cfg_.lidar_timeout_ms;
}

bool FollowFsm::is_theta_jump(const Input &in) {
  if (!in.visual_valid) {
    return false;
  }
  if (!has_prev_theta_) {
    prev_theta_rad_ = in.visual_theta_rad;
    has_prev_theta_ = true;
    return false;
  }

  double jump_rad = std::abs(in.visual_theta_rad - prev_theta_rad_);
  double jump_deg = jump_rad * 180.0 / M_PI;
  prev_theta_rad_ = in.visual_theta_rad;

  return jump_deg > cfg_.max_target_jump_deg;
}

}  // namespace kt_visual_lidar_follow

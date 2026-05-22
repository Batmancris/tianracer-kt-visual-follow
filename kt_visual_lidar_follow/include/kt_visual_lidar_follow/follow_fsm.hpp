#ifndef KT_VISUAL_LIDAR_FOLLOW__FOLLOW_FSM_HPP_
#define KT_VISUAL_LIDAR_FOLLOW__FOLLOW_FSM_HPP_

#include "kt_visual_lidar_follow/follow_types.hpp"

#include <cstdint>

namespace kt_visual_lidar_follow {

struct FsmConfig {
  double desired_distance_m   = 1.2;
  double min_safe_distance_m  = 0.6;
  double max_follow_distance_m = 3.0;
  double angle_window_deg     = 8.0;
  double max_target_jump_deg  = 20.0;
  int    visual_timeout_ms    = 500;
  int    lidar_timeout_ms     = 300;
  int    lidar_hold_timeout_ms = 800;
  double linear_kp            = 0.3;
  double angular_kp           = 0.8;
  double max_linear_debug     = 0.15;
  double max_angular_debug    = 0.4;
};

class FollowFsm {
 public:
  void configure(const FsmConfig &cfg);

  struct Input {
    bool   visual_valid     = false;
    double visual_theta_rad = 0.0;
    double visual_stamp_sec = 0.0;
    double visual_confidence = 0.0;

    bool   lidar_associated = false;
    double lidar_distance_m = 0.0;
    double lidar_stamp_sec  = 0.0;
    int    lidar_valid_count = 0;

    bool   camera_info_ok   = false;
    bool   scan_timeout     = false;

    double current_time_sec = 0.0;
  };

  struct Output {
    FollowState state = FollowState::IDLE;
    FollowCmd   cmd;
    const char *stop_reason = nullptr;
  };

  Output update(const Input &in);

  FollowState state() const { return state_; }

 private:
  FollowState state_ = FollowState::IDLE;
  FsmConfig cfg_;

  double prev_theta_rad_ = 0.0;
  bool   has_prev_theta_ = false;
  double last_visual_stamp_sec_ = 0.0;
  double last_lidar_stamp_sec_  = 0.0;
  double last_lidar_distance_m_ = 0.0;
  double last_lidar_theta_rad_  = 0.0;
  bool   has_last_lidar_ = false;

  void transition_to(FollowState new_state);
  bool check_stop_conditions(const Input &in, const char *&reason);
  bool is_visual_timeout(const Input &in) const;
  bool is_lidar_timeout(const Input &in) const;
  bool is_theta_jump(const Input &in) const;
};

}  // namespace kt_visual_lidar_follow

#endif  // KT_VISUAL_LIDAR_FOLLOW__FOLLOW_FSM_HPP_

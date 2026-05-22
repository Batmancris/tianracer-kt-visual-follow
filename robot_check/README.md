# TianRacer Check (自检系统)

功能包 `robot_check` 提供了一套标准化的机器人开机自检流程，旨在验证 TianRacer 机器人的硬件连接、传感器数据质量、系统 TF 变换及运动控制能力。

该系统设计为“开机即测，测完即停”，适合集成到机器人的启动流程中，生成可视化的状态报告。

## 主要特性

*   **多维度检测**: 覆盖传感器数据频率/帧ID检查、TF 坐标树一致性检查、以及开环/闭环运动响应测试。
*   **结果可判定**: 内置标准化判定逻辑 (PASS/FAIL)，依据配置文件中的阈值自动判断系统健康度。
*   **跨平台架构**: 采用适配器模式 (Adapter Pattern) 设计，核心业务逻辑与底层中间件解耦。目前已内置 ROS1 实现，架构上支持扩展 ROS2。
*   **自动化日志**: 自动在 `reports/` 目录下生成带时间戳的详细运行日志，并具备自动轮转清理功能（默认保留最新 20 份）。
*   **全自动生命周期**: 支持通过 Systemd 实现开机自启，并在测试脚本执行完毕后自动触发 Launch退出。

## 目录结构

```text
robot_check/
├── config/
│   └── check_params.yaml    # 核心配置文件 (阈值、话题名、测试开关)
├── launch/
│   └── auto_check.launch    # 自动测试启动入口
├── reports/                 # [自动生成] 存放测试日志文件
├── scripts/
│   ├── run_all_checks.py    # 测试主程序 (Test Runner)
│   └── robot_check.service # Systemd 服务模板
├── src/robot_check/     # Python 核心库
│   ├── core/                # 业务逻辑层 (Checkers)
│   ├── platform/            # 接口适配层 (ROS1 Implementation)
│   └── logger.py            # 日志管理模块
├── CMakeLists.txt
├── package.xml
└── README.md
```

## 快速开始

### 1. 编译
由于新增了 Python 模块依赖，首次使用请进行编译并刷新环境：
```bash
cd ~/tianracer_ros1_ws
catkin_make
source devel/setup.bash
```

### 2. 手动运行测试
使用 `roslaunch` 启动自检程序：
```bash
roslaunch robot_check auto_check.launch
```
程序将依次执行配置中的检查项，并在终端输出进度。运行结束后，节点会自动退出。

### 3. 查看报告
测试结果将保存在 `reports/` 目录下，文件名为 `YYYYMMDD_HHMMSS.log`。
日志包含详细的 PASS/FAIL 判定及相关指标（如实际 Hz、标准差）。

**日志示例**:
```text
[INFO] ====== Starting Passive Sensor Checks ======
[INFO] Checking /scan ...
[INFO] [Topic_/scan] >>> PASS <<< | hz=10.12, std=0.005, frame=laser
...
[ERROR] [Topic_/odom] >>> FAIL <<< | reason: Low Hz (0.0 < 10.0)
```

## 如何分析测试日志

自检完成后，请查看 `reports/` 目录下的最新日志文件。以下是重点关注指标：

### 1. 传感器部分 (Passive Checks)
*   **状态**: 必须为 `PASS`。
*   **Hz**: 实际频率应在 `min_hz` 之上。如果是激光雷达，通常应为 10Hz 左右；IMU 通常较高。
*   **Jitter (抖动)**: 如过大说明系统负载高或驱动不稳定。

### 2. 运动部分 (Motion Checks)
此部分包含两类测试：前后移动 (Linear) 和 90度转向 (Angular)。

#### Linear (前后移动)
*   **Odom Accuracy**: 检查里程计测量的距离与 Lidar 观测到的环境距离变化是否一致。如果此处 FAIL，说明轮子打滑严重或轮胎半径标定错误。
*   **Straightness**: 检查是否走直线。

#### Angular (90度转向)
由于阿克曼底盘特性，此测试的判定逻辑较为复杂：
*   **Motion_Angular_Rotation**:
    *   **IMU_Deg**: 重点看此值是否接近 90.0°。这是判断转向是否成功的金标准。
    *   **Sync (Odom vs IMU)**: 阿克曼车型由于模型原因，Odom 角度在低速大转向时极易产生巨大漂移（日志中可能显示 WARN 或 FAIL）。**只要 IMU 状态为 PASS，Odom 的失败通常可忽略** (日志会标记 `note: Odom drifted but IMU valid`)。
*   **Motion_Angular_Geometry**:
    *   **Check A/B**: 利用激光雷达校验转向前后的墙面距离一致性。
    *   **B_Status**: 由于转向伴随位移，X轴方向的校验 (Check B) 可能出现 "Warn (Drift)"，这是正常的几何误差，主要关注 Check A (Y轴/侧向墙面) 是否一致。

**PASS 判定原则**:
*   对于转向测试，只要 **IMU 角度达标** 且 **未发生碰撞** (Lidar数据有效)，即使 Odom 数据漂移，也被视为通过。

## 配置说明

所有测试参数均在 `config/check_params.yaml` 中管理：

*   **global**: 全局设置，如日志保留数量。
*   **passive_checks**: 定义需要检查的传感器话题。
    *   `min_hz`: 最小允许频率。
    *   `max_jitter`: 最大允许时间间隔标准差。
    *   `check_frame_id`: 是否检查 frame_id 非空。
*   **motion_check**: 运动测试配置。
    *   **enabled**: `true`/`false`。**默认关闭**以确保安全。开启前请确保机器人在空旷区域或架空。
*   **tf_check**: 需要验证的 TF 变换对列表（如 `map` -> `odom`）。

## 部署开机自启

如果需要将自检程序设置为系统服务（开机自动运行）：

1.  **安装服务文件**:
    修改 `scripts/robot_check.service` 中的路径以匹配您的实际安装位置，然后复制到系统目录：
    ```bash
    sudo cp src/tianracer/robot_check/scripts/robot_check.service /etc/systemd/system/
    ```

2.  **启用服务**:
    ```bash
    sudo systemctl daemon-reload
    sudo systemctl enable robot_check.service
    ```

    下次重启后，系统将自动在后台运行自检，并生成日志报告。可以通过 `journalctl -u robot_check -f` 查看实时输出。

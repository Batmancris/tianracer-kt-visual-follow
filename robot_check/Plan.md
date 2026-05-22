# robot_check 日志系统实施计划

为了实现测试过程的自动化记录，并按照运行时间戳生成日志文件，本计划将构建一个标准化的 Python 日志模块。

## 目标
执行测试脚本后，自动在 `robot_check/reports` 目录下生成日志文件，文件名为 `YYYYMMDD_HHMMSS.log`，内容包含测试过程的详细输出。

## 实施步骤

### 1. 构建 Python 包结构
遵循 ROS 的 Python 模块规范，将通用功能封装为库，供所有测试脚本调用。

*   **创建目录**: `src/robot_check/`
*   **创建文件**: `src/robot_check/__init__.py` (空文件，标识为 Python 包)

### 2. 实现核心日志模块 (`src/robot_check/logger.py`)
创建一个 `CheckLogger` 类，包含以下功能：
*   **路径处理**: 使用 `rospkg` 自动定位 `robot_check` 包的路径，确保无论在何处运行脚本，日志都能准确写入 `reports` 目录。
*   **文件命名**: 使用 `datetime` 生成当前时间戳作为文件名。
*   **双重输出**: 实现 `log()` 方法，同时将信息打印到终端（Terminal）并追加写入到日志文件。

### 3. 配置编译系统
为了让 ROS 识别并安装我们创建的 Python 包，需要修改构建配置。

*   **添加 `setup.py`**:
    在包根目录下创建标准的 `distutils` 安装脚本。
    ```python
    from distutils.core import setup
    from catkin_pkg.python_setup import generate_distutils_setup

    d = generate_distutils_setup(
        packages=['robot_check'],
        package_dir={'': 'src'}
    )
    setup(**d)
    ```

*   **修改 `CMakeLists.txt`**:
    启用 Python 安装宏：
    ```cmake
    catkin_python_setup()
    ```

### 4. 集成与验证
修改现有的测试脚本（如 `scripts/hardware/wifirssi.py`）来使用新模块。

*   **引入**: `from robot_check.logger import CheckLogger`
*   **初始化**: `logger = CheckLogger("WifiTest")`
*   **使用**: `logger.log("开始测试 WiFi 信号...")`

## 预期效果
运行脚本后：
1.  终端实时显示测试进度。
2.  `reports/` 目录下新增如 `20260108_103000.log` 的文件。
3.  日志文件中包含完整的测试记录。

# ROS1/ROS2 核心逻辑解耦架构计划

为了应对机器人中间件升级需求，将通过**适配器模式 (Adapter Pattern)** 重构核心代码，实现业务逻辑与底层通信机制的彻底解耦。

## 架构设计

采用三层架构模式：

1.  **业务逻辑层 (Core Logic)**: 纯 Python 代码，无 ROS 依赖。
2.  **适配接口层 (Interface Layer)**: 定义标准化的抽象基类。
3.  **实现层 (Implementation Layer)**: 针对 ROS1/ROS2 的具体封装。

## 新增目录结构

```text
src/robot_check/
├── __init__.py
├── core/                <-- [纯净区] 业务逻辑
│   ├── __init__.py
│   ├── checkers.py      # 通用检查规则 (如: 阈值判定)
│   └── report_gen.py    # 报告生成器
└── platform/            <-- [适配区] 通信中间件适配
    ├── __init__.py      # 工厂方法: 自动检测 ROS_VERSION 并返回对应实例
    ├── base.py          # 抽象基类定义 (Interface)
    ├── ros1_impl.py     # rospy 实现
    └── ros2_impl.py     # rclpy 实现
```

## 实施步骤

### 1. 定义统一接口 (`src/robot_check/platform/base.py`)
定义所有测试脚本需要用到的底层能力接口：
*   `get_time()`: 获取系统/ROSTime
*   `get_topic_list()`: 获取当前活跃话题列表
*   `log_info(msg)`: 统一日志输出接口
*   `sleep(duration)`: 统一休眠接口

### 2. 实现工厂模式 (`src/robot_check/platform/__init__.py`)
通过环境变量自动加载对应后端：
```python
import os
import importlib

def get_platform_interface():
    res = os.environ.get('ROS_VERSION', '1') # 默认为 1
    if res == '1':
        return importlib.import_module('.ros1_impl', package='robot_check.platform').ROS1System()
    elif res == '2':
        return importlib.import_module('.ros2_impl', package='robot_check.platform').ROS2System()
```

### 3. 重构现有脚本
将 `scripts/` 下的脚本（如 `topic_check.py`）改造为调用 `get_platform_interface()`，移除所有直接的 `import rospy`。

## 优势
*   **兼容性**: 一套代码库同时支持 ROS1 Noetic 和 ROS2 Humble。
*   **可测试性**: 业务逻辑层不依赖 ROS 环境，可直接在 CI 流程中进行单元测试。

# 开机自检与生命周期管理计划

为满足“开机即测，测完即停”的需求，需要建立主控运行机制与系统级自启动配置。

## 1. 统一运行入口 (Test Runner)
创建一个主控脚本 `scripts/run_all_checks.py`，作为自检程序的唯一入口。

*   **职责**:
    1.  **调度**: 依次加载并执行硬件、集成、系统层的测试逻辑。
    2.  **聚合**: 收集分散的测试结果。
    3.  **报告**: 调用 `CheckLogger` 生成最终的汇总报告文件。
    4.  **自停**: 执行完毕后主动调用 `sys.exit(0)` 退出进程，并通知 ROS Master（如果是 Launcher 启动）。

## 2. Launch 文件配置
创建 `launch/auto_check.launch`，赋予程序在 ROS 环境中的启动能力。

```xml
<launch>
    <!-- 设置参数：是否并在测试结束后自动关闭节点 -->
    <arg name="auto_close" default="true" />

    <!-- 启动测试节点 -->
    <node pkg="robot_check" type="run_all_checks.py" name="robot_checker" output="screen" required="true">
        <param name="auto_close" value="$(arg auto_close)" />
    </node>
</launch>
```
*   **required="true"**: 关键属性。当该节点（测试脚本）运行结束退出时，会触发整个 launch 进程退出，实现“测完即停”。

## 3. 开机自启配置 (Systemd)
推荐使用 Linux 标准的 Systemd 服务来实现开机自启。

*   **服务文件**: `/etc/systemd/system/robot_check.service`
*   **配置模板**:
    ```ini
    [Unit]
    Description=TianRacer Auto Check Service
    # 确保在网络和 ROS 核心服务（如果有）之后启动
    After=network.target docker.service

    [Service]
    Type=oneshot
    User=sunrise
    # 加载环境并执行 Launch
    ExecStart=/bin/bash -c "source /home/sunrise/tianracer_ros1_ws/devel/setup.bash && roslaunch robot_check auto_check.launch"
    # 关键：运行一次后即视为完成，不自动重启
    Restart=no
    # 保留日志输出到 journalctl
    StandardOutput=journal

    [Install]
    WantedBy=multi-user.target
    ```

## 实施路线
1.  先完成 **Python 包与日志模块** 的开发。
2.  开发 **Test Runner** 逻辑，串联各个测试脚本。
3.  编写 **Launch 文件** 并测试手动运行效果。
4.  最后配置 **Systemd** 进行开机自启实测。

# 配套设施与健壮性完善

为确保自检程序适应“无头模式”运行环境并具备长期可靠性，需补充以下机制。

## 1. 配置文件管理 (Configuration)
将硬编码的阈值剥离到配置文件中，便于针对不同硬件版本进行微调。

*   **文件**: `config/check_params.yaml`
*   **内容示例**:
    ```yaml
    wifi:
      min_rssi: -75
      target_ssid: "TianBot_Office"
    topics:
      timeout: 3.0  # 秒
      required:
        - name: /scan
          min_hz: 5.0
        - name: /imu/data
    ```
*   **加载**: 在 `checkers.py` 初始化时读取 ROS 参数服务器或直接加载 YAML 文件。

## 2. 人机交互反馈 (HMI Feedback)
在没有屏幕的情况下，通过声音或灯光告知用户自检结果。

*   **接口扩展**: 在 `platform/base.py` 中增加反馈接口：
    *   `set_led(color, mode)`: 控制板载 LED (如 breathe/blink)。
    *   `beep(count, duration)`: 控制蜂鸣器。
*   **策略**:
    *   **启动时**: 蜂鸣器短鸣 1 声。
    *   **通过**: 蜂鸣器长鸣 1 声，LED 转绿。
    *   **失败**: 蜂鸣器急促 3 声，LED 转红闪烁。

## 3. 日志轮转机制 (Log Rotation)
防止日志文件无限堆积占用磁盘空间。

*   **策略**: 在 `CheckLogger` 初始化时执行清理。
*   **逻辑**: 扫描 `reports/` 目录，按时间排序，保留最新的 20 个文件，删除其余旧文件。

## 4. 超时看门狗 (Watchdog)
防止因传感器驱动挂死导致自检程序永久阻塞。

*   **全局超时**: Systemd 配置 `RuntimeMaxSec=60s`，超时强制杀掉。
*   **单项超时**: 在 `TestRunner` 中使用装饰器或 `func_timeout` 库，限制每个测试用例的最大运行时间（如 WiFi 检查不超过 5 秒）。

## 补充：判定规则、阈值与实现注意事项

为便于实现与评估一致性，以下判定规则应写入 `config/check_params.yaml` 并在 `Plan.md` 中做为标准说明：

- **被动传感器可用性（摄像头/雷达/IMU/ODOM/电池）**：
  - 采样窗口：默认 5 秒或至少 20 条消息（先到者）。
  - 通过条件：接收消息数 / 时间 >= `min_hz`，且 `std`（时间间隔标准差） <= `max_jitter`。
  - 附加检查：`header.frame_id` 非空，消息内容非全 NaN（例如 laser ranges 有有效测距值，image 有非零尺寸）。

- **数据链路完整性**：
  - 以实际订阅并在 `topics.timeout` 秒内收到首条消息作为“链路存在”的判定。
  - 可选增强：通过 `rospy.get_published_topics()` 或 `rosnode`/`rosmaster` 查询发布者列表以诊断具体节点名。

- **/tf 树完整性**：
  - 对所有在消息 `header.frame_id` 中出现的 frame，执行 `lookup_transform(frame, base_frame, now)`（允许短超时），若失败则标记为缺失。

- **前后与转向运动测试（运动验证）**：
  - 前后移动：记录运动前后 `odom.pose`（position + quaternion）与 `scan` 在前方/侧方角度窗口的最小距离，判定条件：|odom_delta_linear - measured_lidar_delta| <= `pos_tol`。
  - 转向：计算前后 yaw 差（处理 wrap-around），判定条件：|yaw_delta - expected_deg| <= `ang_tol`，并交叉比较激光在不同角度的距离变化是否符合同步旋转预期。
  - 建议容忍度：位置误差 `pos_tol` 初始设为 0.15m，角度误差 `ang_tol` 初始设为 5°（可配置）。
  - 强制安全：动作测试必在无障碍/仿真环境执行，或在执行前检查前方 `scan` 最小距离 > `safe_dist`。

- **运动控制是否被接收与执行**：
  - 在发送控制命令后，验证 `odom` 与 `scan` 在短时间窗口内出现对应变化；若无变化，标记控制未执行或被下层安全策略截断。

- **日志与报告输出**：
  - 最终报告同时输出机器可解析格式（JSON/YAML）和人类可读摘要，包含每项测试的 PASS/FAIL、采样数、均值、标准差、时间戳与简短错误说明。

### 实现注意事项与风险

- 时间同步问题：如果各设备使用不同时钟，优先使用接收时间并记录 header.stamp 与接收时间差以便离线分析。
- 里程计与激光存在固有噪声与漂移，运动测试结果应以容忍度与多次试验的统计结论为准。
- 对于链路诊断，完全凭被动观察判断“无订阅者”有时不可靠；更可行的目标是“topic 有持续稳定发布”。

# 激光雷达辅助高精度运动校验计划

在完成基础的 Motion Check 逻辑后，我们利用激光雷达（Lidar）作为外部参考真值，对机器人的里程计精度和运动控制稳定性进行更严格的校验。

## 目标

利用高精度的激光测距数据，实现以下两点高级校验功能：

1.  **里程计精度校验 (Odom Verification)**: 通过比较“激光测量的物理移动距离”与“轮式里程计报告的移动距离”，判断底盘编码器/运动学解算的准确性。
2.  **直线行驶稳定性校验 (Straightness Verification)**: 通过监测车身侧向（Left/90°）距离在运动过程中的变化，判断机器人在开环控制下的直线保持能力。

## 实施方案

### 1. 里程计精度校验 (Linear Motion Accuracy)

*   **原理**: 在机器人正前方存在静态障碍物（如墙壁）的前提下，机器人前进距离 $\Delta d_{odom}$ 应严格等于激光雷达前方距离的减少量 $\Delta d_{lidar}$。
*   **计算公式**:
    *   $\Delta d_{lidar} = d_{front\_start} - d_{front\_end}$
    *   $\Delta d_{odom} = \text{Calculate from Encoder/Odom Topic}$
    *   **误差**: $E_{odom} = |\Delta d_{odom} - \Delta d_{lidar}|$
*   **判定标准**:
    *   若 $d_{front\_start}$ 或 $d_{front\_end}$ 为 `inf`（无效），则**跳过**此高精度检查，仅保留原有的“是否有速度反馈”检查。
    *   若数据有效，且 $E_{odom} < \text{tolerance}$ (例如 0.05m)，则判定里程计精度 **PASS**。
    *   否则判定 **FAIL** (可能是轮子打滑、编码器比例错误或ROS参数配置错误)。

### 2. 直线保持能力校验 (Straight Line Stability)

*   **原理**: 在机器人左侧存在近似平行墙壁（走廊环境常见）的前提下，做直线运动时，左侧激光距离应保持恒定。
*   **采样策略**:
    *   **Start 时刻**: 记录 $d_{left\_start}$
    *   **Mid 时刻** (可选，需修改执行逻辑): 记录 $d_{left\_mid}$
    *   **End 时刻**: 记录 $d_{left\_end}$
*   **计算公式**:
    *   **漂移量 (Drift)**: $D_{lat} = |d_{left\_start} - d_{left\_end}|$
*   **判定标准**:
    *   若激光数据无效，**跳过**此检查。
    *   若 $D_{lat} < \text{tolerance}$ (例如 0.1m/5m)，则判定直线行走稳定性 **PASS**。
    *   若偏差过大，说明机器人在此地面存在严重的跑偏现象（左右轮摩擦力不均、机械结构问题或电机差异）。

## 补充思考与应用场景

1.  **环境自适应**: 算法必须先检查环境特征（"前方是否有并在量程内的墙？", "左侧是否有长墙？"）。如果不满足环境条件，自动降级为普通检查，避免误报 FAIL。
2.  **安全性增强**: 如果在测试过程中 $d_{front}$ 急剧减小并低于安全阈值（例如 0.3m），测试脚本应触发**紧急刹车**，而不是盲目走完设定时间。
3.  **开发计划**:
    *   在 `robot_check/core/checkers.py` 中扩展 `run_motion_checks`。
    *   增加 `tolerance` 参数到 `check_params.yaml`。
    *   增加“中间时刻采样”逻辑（可能需要将 sleep 改为循环采样）。

# 多模态融合转向精度校验计划

在“前后与转向运动测试”的基础上，引入点云几何约束与 IMU/Odom 交叉验证机制，进一步量化机器人的原地转向精度与位姿解算一致性。

## 目标
1. **几何一致性校验**: 利用环境墙面作为静态参考系，通过转向前后激光点云对同一物理平面的观测变化，校验机器人实际物理转角是否准确。
2. **多传感器姿态一致性**: 校验轮式里程计 (Odom) 与 惯性测量单元 (IMU) 在大幅度动态转向过程中的输出是否同步且一致。

## 实施流程 (Verification Pipeline)

该测试接续在“前进后退能力校验”之后执行，假设环境具备一定几何特征（如角落或有明确边角的场景）。

### 1. 状态采样 (Point 1)
在完成直线测试并静止后，记录当前状态 $S_1$:
- **Laser**:
  - $d_{front\_1}$: 前向 (0°) 激光测距值。
  - $d_{left\_1}$: 左向 (+90°) 激光测距值。
- **Odom**: 位置 $(x_1, y_1)$，姿态四元数 $q_{odom\_1}$ (需转换为欧拉角 $yaw_{odom\_1}$)。
- **IMU**: 姿态四元数 $q_{imu\_1}$ (需转换为欧拉角 $yaw_{imu\_1}$)。

### 2. 执行动作
控制机器人原地旋转 +90° (左转)。
- 目标：使车身坐标系逆时针旋转 90 度。

### 3. 结果采样 (Point 2)
运动结束并从静止稳定后，记录当前状态 $S_2$:
- **Laser**:
  - $d_{front\_2}$: 前向 (0°) 激光测距值。
  - $d_{right\_2}$: 右向 (-90°) 激光测距值。 (注意：车身转过90度后，原来的前方墙面应该在现在车身的右侧；原来的左侧墙面应该在现在的正前方)。
- **Odom**: 位置 $(x_2, y_2)$，姿态四元数 $q_{odom\_2}$ ($yaw_{odom\_2}$)。
- **IMU**: 姿态四元数 $q_{imu\_2}$ ($yaw_{imu\_2}$)。

## 校验逻辑 (Validation Logic)

### A. 几何闭环校验 (Geometry Consistency)
利用 Odom 的位置增量补偿机器人自身的微小位移，验证环境观测的一致性。

*注意：坐标系定义以初始 Odom 坐标系为准，若机器人起始未与轴线完全对齐，以下公式通过位置增量 ($\Delta x, \Delta y$) 进行补偿。*

1. **左侧墙面一致性 (Check: Left Wall -> Front)**
   - **逻辑**: 点1的左侧墙面 ($d_{left\_1}$) 应该等于 点2的前向墙面 ($d_{front\_2}$) 加上机器人在该方向上的位移。
   - **公式**:
     - 假设 Odom 坐标系 Y 轴大致指向左侧墙面：
     - $Val_A = |(d_{front\_2} + (y_2 - y_1)) - d_{left\_1}|$
     - **判定**: $|Val_A| < \text{tolerance}_{geo}$ (考虑墙面不完全垂直因素，容差设为 0.1m)。
   - **修正说明**: 原始思路中提及“x的差值”，但涉及左侧墙面（Y轴方向）通常关联 Y 轴坐标变化。若环境坐标系未对齐，需使用向量投影，但在此简化为轴向校验。

2. **前向墙面一致性 (Check: Front Wall -> Right)**
   - **逻辑**: 点1的前向墙面 ($d_{front\_1}$) 应该等于 点2的右侧墙面 ($d_{right\_2}$) 加上机器人在该方向上的位移。
   - **公式**:
     - 假设 Odom 坐标系 X 轴大致指向前向墙面：
     - $Val_B = |(d_{right\_2} + (x_2 - x_1)) - d_{front\_1}|$
     - **判定**: $|Val_B| < \text{tolerance}_{geo}$。

### B. 姿态传感器一致性 (Orientation Consistency)
1. **Odom 转向角精度**:
   - $\Delta yaw_{odom} = Normalize(yaw_{odom\_2} - yaw_{odom\_1})$
   - **判定**: $|\Delta yaw_{odom} - 90^\circ| < \text{tolerance}_{angle}$ (例如 5°)。

2. **IMU 转向角精度**:
   - $\Delta yaw_{imu} = Normalize(yaw_{imu\_2} - yaw_{imu\_1})$
   - **判定**: $|\Delta yaw_{imu} - 90^\circ| < \text{tolerance}_{angle}$。

3. **传感器互验**:
   - **判定**: $|\Delta yaw_{odom} - \Delta yaw_{imu}| < \text{tolerance}_{sync}$ (例如 3°)。用于检测里程计打滑或 IMU 漂移。

## 补充说明与潜在问题
1. **激光数据的稳定性**: 单束激光容易受噪点影响，实际工程中应取目标方向 $\pm 2^\circ$ 范围内的均值或中位数。
2. **环境依赖性**: 此几何校验强依赖于环境存在“左侧墙”和“前方墙”。若 $d_{left\_1}$ 或 $d_{front\_1}$ 超出量程 (inf)，则逻辑 A 自动跳过，仅执行逻辑 B。
3. **坐标轴定义的修正**:
   - 物理实际上：左侧墙面距离变化对应 Y 轴位移，前方墙面距离变化对应 X 轴位移。本计划已对此进行修正。

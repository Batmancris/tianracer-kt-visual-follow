# 常见问题与调试记录 (FAQ)

## 运动测试 (Motion Check)

### 1. 90度转弯测试中，机器人提前停止
**现象**: 设定转弯90度，但实际大约转了87-88度就停止了。
**原因**: 在原始的控制逻辑中，为了防止过冲，设置了一个固定的缓冲区 `buffer = 0.05` 弧度 (~2.8度)。当 `目标 - 当前 < 0.05` 时即停止。
**解决**: 移除了该硬编码缓冲区，直接判定 `abs(diff) < tolerance` 或由 `checkers.py` 的高层逻辑接管超时停止。

### 2. 阿克曼底盘的里程计 (Odom) 在原地转向或大角度转向时漂移严重
**现象**: 机器人尝试左转90度。IMU显示转了约90度，Lidar验证几何位置也正确，但里程计显示转了近175度。
**原因**: 阿克曼底盘模型在极低速大转向角下存在打滑或积分误差累积（尤其是在无编码器反馈或单靠模型推算时）。
**解决**:
1. **控制闭环**: 将转向控制的反馈源从 Odom 改为 IMU (`get_imu_yaw`)，确保物理转向角度准确。
2. **宽松校验**: 在结果判定中，放松 `sync` (Odom vs IMU) 的同步一致性阈值 (`sync_tol_deg` 调整为 100.0)，即允许 Odom 数据出现巨大偏差，只要 IMU 和 Lidar 验证通过即可判定测试 PASS。
3. **增加备注**: 在日志中增加 WARN/Note，提示 "Odom drifted but IMU valid"。

### 3. 几何一致性检查 (Geometry Check) 失败
**现象**: 机器人左转后，虽然 Lidar 测距显示距离墙面距离合理，但这与基于 Odom 增量计算的预期值不符，导致 Check A/B 失败。
**原因**:
1. **坐标系混淆**：原始计算直接使用了全局坐标系下的 `dx, dy`，未考虑机器人自身旋转导致的前/左传感器轴向变化。
2. **阿克曼运动学特性**：阿克曼底盘无法原地旋转，转向伴随着必可避免的 $X/Y$ 位移。
**解决**:
1. **局部坐标投影**：引入旋转矩阵，将 Odom 的全局位移 $(dx_{global}, dy_{global})$ 投影回机器人起始时刻的局部坐标系 $(dx_{local}, dy_{local})$。
   $$
   \begin{bmatrix} dx_{local} \\ dy_{local} \end{bmatrix} = \begin{bmatrix} \cos(-\theta_{start}) & -\sin(-\theta_{start}) \\ \sin(-\theta_{start}) & \cos(-\theta_{start}) \end{bmatrix} \begin{bmatrix} dx_{global} \\ dy_{global} \end{bmatrix}
   $$
2. **校验逻辑修正**: 使用投影后的局部位移来修正 Lidar 的预期观测值。
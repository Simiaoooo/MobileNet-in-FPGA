# Baseline vs Optimized 对比指南

> **快速查看优化效果的完整工具链**

---

## 🎯 对比工具清单

| 工具 | 功能 | 使用场景 |
|------|------|---------|
| **[quick_compare.py](quick_compare.py)** | 快速查看关键指标 | ⭐ 日常快速检查 |
| **[benchmark_performance.py](benchmark_performance.py)** | 性能基准测试 | 生成性能数据 |
| **[compare_baseline_vs_optimized.py](compare_baseline_vs_optimized.py)** | 完整对比报告 | 详细分析 |

---

## 🚀 快速开始（3 步）

### 第 1 步：测试 Baseline 性能

```bash
# 确保在 baseline 版本（未优化）
python benchmark_performance.py --mode baseline

# 输出：baseline_results/performance.json
```

**预期输出：**
```
FPS:          40.00
平均延迟:     25.00 ms
内存带宽:     1200.00 MB/s
```

### 第 2 步：集成优化并测试

```bash
# 自动集成优化
python auto_integrate_optimizations.py

# 编译（使用您的工具链）
cd verilog/MobileNet_v3_conv_8_3x1
quartus_sh --flow compile ../../project.qpf

# 测试优化版性能
cd ../..
python benchmark_performance.py --mode optimized

# 输出：optimized_results/performance.json
```

**预期输出：**
```
FPS:          120.00  (3× 提升)
平均延迟:     8.33 ms (67% 减少)
内存带宽:     300.00 MB/s (75% 减少)
```

### 第 3 步：查看对比

```bash
# 快速查看（推荐）
python quick_compare.py

# 完整报告（详细分析）
python compare_baseline_vs_optimized.py
```

**快速查看输出示例：**
```
====================================================================
  MobileNet FPGA 优化效果速览
====================================================================

📊 性能对比
----------------------------------------------------------------------
指标                 Baseline        Optimized       改进
----------------------------------------------------------------------
FPS                     40.00          120.00        🚀 3.00×
延迟 (ms)               25.00            8.33        ⬇️  66.7%
带宽 (MB/s)           1200.0           300.0        ⬇️  75.0%

✅ FPS 提升达标（目标：3-4×）
✅ 内存带宽减少达标（目标：78%）

🔍 各层优化效果（Top 5）
----------------------------------------------------------------------
层名                           Baseline (ms)   Optimized (ms)   改进
----------------------------------------------------------------------
conv1_dw                              5.20            0.80      🚀  84.6%
conv2_dw                              4.80            0.75      🚀  84.4%
conv3_dw                              3.50            0.60      🚀  82.9%
conv1_pw                              3.20            1.20      ⬆️  62.5%
conv2_pw                              2.80            1.10      ⬆️  60.7%
```

---

## 📊 详细对比报告

### 运行完整对比

```bash
python compare_baseline_vs_optimized.py
```

### 输出文件

1. **comparison_report.md** - Markdown 格式报告
2. **comparison_data.json** - 原始 JSON 数据
3. **comparison_report.html** - HTML 可视化报告（可选）

### 报告内容

```markdown
# MobileNet FPGA 优化对比报告

## 📊 执行摘要

### 资源使用
| 资源类型 | Baseline | Optimized | 变化 |
|---------|----------|-----------|------|
| 逻辑单元 (LE) | 250,000 (83%) | 270,000 (90%) | +8.0% |
| BRAM (bits) | 12,000K (86%) | 12,500K (90%) | +4.2% |
| Fmax (MHz) | 100.00 | 102.50 | +2.50 |

### 性能提升
| 指标 | Baseline | Optimized | 改进 |
|------|----------|-----------|------|
| FPS | 40.00 | 120.00 | 3.00× |
| 延迟 (ms) | 25.00 | 8.33 | 66.7% ↓ |

### 功能正确性
- 测试通过率: 100.0%
- 最大输出差异: 0.000001

## 🎯 优化目标达成情况
| 优化目标 | 目标值 | 实际值 | 状态 |
|---------|--------|--------|------|
| FPS 提升 | 3-4× | 3.00× | ✅ 达成 |
| 内存带宽减少 | 78% | 75.0% | ⚠️ 接近 |
| 资源增加 | <10% | +8.0% | ✅ 符合 |
```

---

## 🔧 在 FPGA 上测试（实际硬件）

### 方法 1: 通过串口通信测试

如果您的项目使用 UART 通信（参考 [utils/send_data_UART.py](utils/send_data_UART.py)）：

```python
# 修改 benchmark_performance.py 以支持 FPGA
import serial
import struct

class FPGAModel:
    def __init__(self, port='COM3', baudrate=3000000):
        self.ser = serial.Serial(port, baudrate, timeout=1)

    def predict(self, images, verbose=0):
        results = []
        for img in images:
            # 发送图像数据
            img_data = (img * 255).astype(np.uint8).flatten()
            self.ser.write(img_data.tobytes())

            # 接收结果
            result_bytes = self.ser.read(10 * 4)  # 10 个 float32
            result = struct.unpack('10f', result_bytes)
            results.append(result)

        return np.array(results)

# 使用 FPGA 模型
model = FPGAModel(port='COM3')
python benchmark_performance.py --mode optimized  # 使用修改后的脚本
```

### 方法 2: 使用已有的测试脚本

参考项目中的 [r08_prepare_data_for_verilog.py](r08_prepare_data_for_verilog.py)：

```bash
# 1. 准备测试数据
python r08_prepare_data_for_verilog.py

# 2. 在 FPGA 上运行
# （通过 Quartus Programmer 加载 .sof 文件）

# 3. 收集输出结果
# （通过串口或 SignalTap 捕获）

# 4. 手动创建性能文件
cat > baseline_results/performance.json << EOF
{
  "fps": 40.0,
  "latency_ms": 25.0,
  "memory_bandwidth_mb": 1200.0
}
EOF

# 5. 重复步骤 2-4（优化版本）

# 6. 运行对比
python quick_compare.py
```

---

## 📈 对比维度详解

### 1. 性能对比（Performance）

| 指标 | 说明 | 计算方法 |
|------|------|---------|
| **FPS** | 每秒处理帧数 | `总图像数 / 总时间` |
| **延迟** | 单帧处理时间 | `时间测量（ms）` |
| **带宽** | 内存访问速度 | `(输入+权重+输出) × FPS` |

**优化目标：**
- FPS: 3-4× 提升（40 → 120-160）
- 延迟: 70% 减少（25ms → 8ms）
- 带宽: 78% 减少（100% → 22%）

### 2. 资源使用（Resource Utilization）

| 资源 | 说明 | 优化影响 |
|------|------|---------|
| **LE (Logic Elements)** | 逻辑单元 | +5-10% |
| **BRAM** | 片上存储 | +2-5% |
| **Fmax** | 最大频率 | 持平或略增 |

**优化目标：**
- 资源增加 <10%
- Fmax ≥100 MHz

### 3. 功能正确性（Functional Correctness）

| 检查项 | 说明 | 通过标准 |
|--------|------|---------|
| **分类准确率** | 输出类别一致性 | ≥99% |
| **输出差异** | 概率值误差 | <0.01 |
| **逐层输出** | 中间层一致性 | <1% 差异 |

---

## 🎨 可视化对比（高级）

### 生成性能曲线图

```python
# visualize_comparison.py（新建）
import json
import matplotlib.pyplot as plt

# 读取数据
with open('baseline_results/performance.json', 'r') as f:
    baseline = json.load(f)
with open('optimized_results/performance.json', 'r') as f:
    optimized = json.load(f)

# 绘图
fig, axes = plt.subplots(1, 3, figsize=(15, 5))

# FPS 对比
axes[0].bar(['Baseline', 'Optimized'],
            [baseline['fps'], optimized['fps']])
axes[0].set_title('FPS Comparison')
axes[0].set_ylabel('Frames per Second')

# 延迟对比
axes[1].bar(['Baseline', 'Optimized'],
            [baseline['latency_ms'], optimized['latency_ms']])
axes[1].set_title('Latency Comparison')
axes[1].set_ylabel('Milliseconds')

# 带宽对比
axes[2].bar(['Baseline', 'Optimized'],
            [baseline['memory_bandwidth_mb'], optimized['memory_bandwidth_mb']])
axes[2].set_title('Memory Bandwidth')
axes[2].set_ylabel('MB/s')

plt.tight_layout()
plt.savefig('comparison_chart.png', dpi=300)
print("✓ 图表已保存: comparison_chart.png")
```

运行：
```bash
python visualize_comparison.py
```

---

## 🐛 故障排查

### 问题 1: "未找到性能数据"

**原因：** 未运行 benchmark_performance.py

**解决：**
```bash
python benchmark_performance.py --mode baseline
python benchmark_performance.py --mode optimized
```

### 问题 2: "模型加载失败"

**原因：** benchmark_performance.py 需要实际模型

**解决方案 A（使用模拟数据）：**
```python
# 在 benchmark_performance.py 中使用 DummyModel
# 已内置，无需修改
```

**解决方案 B（连接 FPGA）：**
```python
# 实现 FPGAModel 类（见上文"在 FPGA 上测试"）
```

### 问题 3: "输出结果不一致"

**调试步骤：**
1. 检查优化集成是否正确
2. 运行 `line_buffer_tb.v` 验证模块功能
3. 使用 SignalTap 捕获中间信号
4. 逐层对比输出

---

## 📚 完整工作流程示例

### 场景：首次完整对比

```bash
# ========== 准备阶段 ==========
# 1. 备份原始代码
cp -r verilog verilog_backup

# 2. 测试 baseline
python benchmark_performance.py --mode baseline
# 保存输出：baseline_results/performance.json

# ========== 优化阶段 ==========
# 3. 自动集成优化
python auto_integrate_optimizations.py

# 4. 编译优化版本
cd verilog/MobileNet_v3_conv_8_3x1
quartus_sh --flow compile ../../project.qpf
cd ../..

# 5. 测试优化版本
python benchmark_performance.py --mode optimized
# 保存输出：optimized_results/performance.json

# ========== 对比阶段 ==========
# 6. 快速查看
python quick_compare.py

# 7. 详细报告
python compare_baseline_vs_optimized.py
# 生成：comparison_report.md

# 8. 查看报告
cat comparison_report.md
# 或在浏览器打开 HTML 版本
```

### 场景：迭代优化

```bash
# 调整优化参数（如 Line Buffer 宽度）
nano verilog/MobileNet_v3_conv_8_3x1/line_buffer_dwconv.v

# 重新编译
quartus_sh --flow compile project.qpf

# 快速测试
python benchmark_performance.py --mode optimized

# 查看改进
python quick_compare.py
```

---

## 🎯 优化目标检查清单

在运行对比后，使用此清单验证优化效果：

- [ ] **FPS 提升 ≥3×**
  - Baseline: ~40 FPS
  - Target: ≥120 FPS
  - Actual: _____

- [ ] **延迟减少 ≥66%**
  - Baseline: ~25 ms
  - Target: ≤8.5 ms
  - Actual: _____

- [ ] **带宽减少 ≥70%**
  - Baseline: 100%
  - Target: ≤30%
  - Actual: _____

- [ ] **资源增加 <10%**
  - LE 增加: ____%
  - BRAM 增加: ____%

- [ ] **功能正确性 ≥99%**
  - 分类一致率: ____%
  - 最大差异: _____

- [ ] **Fmax 保持 ≥100 MHz**
  - Baseline: _____ MHz
  - Optimized: _____ MHz

---

## 📞 获取帮助

- **文档：** [OPTIMIZATION_PLAN.md](OPTIMIZATION_PLAN.md)
- **快速开始：** [QUICK_START_OPTIMIZATION.md](QUICK_START_OPTIMIZATION.md)
- **实施指南：** [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)

---

**版本：** v1.0
**最后更新：** 2026-02-05

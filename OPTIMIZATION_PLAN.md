# MobileNet FPGA 存储访问优化方案

## 1. 当前 Baseline 分析

### 1.1 Memory Bound 瓶颈识别

基于代码分析（[TOP.v](verilog/MobileNet_v3_conv_8_3x1/TOP.v) 和 [conv_TOP.v](verilog/MobileNet_v3_conv_8_3x1/conv_TOP.v)），识别出以下关键瓶颈：

#### **DWConv 存储瓶颈：**
```verilog
// 当前实现：每个像素都从主存读取 3×3 邻域（9次读取）
// TOP.v:1283 - memstartp_lvl 计算
memstartp_lvl = memstartp + (depthwise? (lvl*matrix2) : ...)
```

**问题：**
- 每处理一个输出像素，需要从主存读取 **9 个输入像素**
- 对于 128×128 的特征图，总读取次数：`128×128×9 = 147,456 次`
- **数据复用率低：** 相邻输出像素的 3×3 窗口有 6 个像素重叠，但被重复读取

#### **PWConv 存储瓶颈：**
```verilog
// 当前实现：8 个输出通道并行，但输入通道串行累加
// conv_TOP.v - onexone 逻辑，每个像素读取所有输入通道
```

**问题：**
- 对于 64 输入通道 → 8 输出通道的 1×1 卷积
- 每个输出像素需要读取 **64 个输入通道** 的同一位置
- 总读取次数：`64×64×64×8 = 2,097,152 次`（假设 64×64 特征图）
- **带宽瓶颈：** 输入特征图被重复读取 8 次（每个输出通道一次）

#### **双缓冲机制的局限：**
```verilog
// TOP.v:119-120 - 双缓冲地址切换
picture_storage_limit = 0;
picture_storage_limit_2 = 128*128*1;
```

**问题：**
- 仅提供层间缓冲，无法复用层内的滑窗数据
- 内存带宽浪费在重复读取相同数据上

---

## 2. 优化方案 1: Line Buffer 设计（DWConv 优化）

### 2.1 设计原理

**核心思想：** 使用 3 行缓冲（Line Buffer）存储当前处理行及其上下相邻行，避免重复访问主存。

```
主存 (Off-chip SDRAM)
    ↓ 按行读取（每行读取一次）
┌─────────────────────────────────┐
│ Line Buffer 0 (Row N-1)         │  ← 上一行
│ Line Buffer 1 (Row N)           │  ← 当前行
│ Line Buffer 2 (Row N+1)         │  ← 下一行
└─────────────────────────────────┘
    ↓ 3×3 窗口滑动
[卷积计算单元]
```

### 2.2 Verilog 实现框架

创建新模块：`line_buffer_dwconv.v`

```verilog
module line_buffer_dwconv #(
    parameter WIDTH = 128,          // 特征图宽度
    parameter DATA_WIDTH = 13,      // 数据位宽
    parameter NUM_CHANNELS = 8      // 并行通道数
)(
    input clk,
    input rst_n,
    input enable,

    // 主存接口（按行读取）
    input [DATA_WIDTH-1:0] mem_data_in,
    output reg mem_read_en,
    output reg [15:0] mem_addr,

    // 3×3 窗口输出（9 个像素 × 8 通道）
    output reg [DATA_WIDTH-1:0] win_00, win_01, win_02,
    output reg [DATA_WIDTH-1:0] win_10, win_11, win_12,
    output reg [DATA_WIDTH-1:0] win_20, win_21, win_22,
    output reg window_valid
);

    // 三行缓冲（使用 BRAM）
    reg [DATA_WIDTH-1:0] line_buf_0 [0:WIDTH-1];
    reg [DATA_WIDTH-1:0] line_buf_1 [0:WIDTH-1];
    reg [DATA_WIDTH-1:0] line_buf_2 [0:WIDTH-1];

    // 滑窗寄存器（3×3）
    reg [DATA_WIDTH-1:0] window [0:2][0:2];

    // 控制逻辑
    reg [7:0] col_cnt;
    reg [7:0] row_cnt;
    reg [1:0] line_sel;  // 循环使用 3 行缓冲

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            col_cnt <= 0;
            row_cnt <= 0;
            line_sel <= 0;
        end else if (enable) begin
            // 读取新列数据
            if (mem_read_en) begin
                case (line_sel)
                    2'd0: line_buf_0[col_cnt] <= mem_data_in;
                    2'd1: line_buf_1[col_cnt] <= mem_data_in;
                    2'd2: line_buf_2[col_cnt] <= mem_data_in;
                endcase
            end

            // 滑窗移动（左移）
            window[0][0] <= window[0][1];
            window[0][1] <= window[0][2];
            window[1][0] <= window[1][1];
            window[1][1] <= window[1][2];
            window[2][0] <= window[2][1];
            window[2][1] <= window[2][2];

            // 加载新列
            case (line_sel)
                2'd0: begin
                    window[0][2] <= line_buf_0[col_cnt];
                    window[1][2] <= line_buf_1[col_cnt];
                    window[2][2] <= line_buf_2[col_cnt];
                end
                2'd1: begin
                    window[0][2] <= line_buf_1[col_cnt];
                    window[1][2] <= line_buf_2[col_cnt];
                    window[2][2] <= line_buf_0[col_cnt];
                end
                2'd2: begin
                    window[0][2] <= line_buf_2[col_cnt];
                    window[1][2] <= line_buf_0[col_cnt];
                    window[2][2] <= line_buf_1[col_cnt];
                end
            endcase

            // 列计数器
            if (col_cnt == WIDTH-1) begin
                col_cnt <= 0;
                row_cnt <= row_cnt + 1;
                line_sel <= (line_sel == 2'd2) ? 2'd0 : line_sel + 1;
            end else begin
                col_cnt <= col_cnt + 1;
            end
        end
    end

    // 输出 3×3 窗口
    assign win_00 = window[0][0];
    assign win_01 = window[0][1];
    assign win_02 = window[0][2];
    assign win_10 = window[1][0];
    assign win_11 = window[1][1];
    assign win_12 = window[1][2];
    assign win_20 = window[2][0];
    assign win_21 = window[2][1];
    assign win_22 = window[2][2];
    assign window_valid = (col_cnt >= 2) && (row_cnt >= 1);

endmodule
```

### 2.3 性能提升分析

**访存次数对比：**

| 方法 | 每像素读取次数 | 128×128 总读取次数 | 带宽需求 |
|------|----------------|-------------------|----------|
| **Baseline（当前）** | 9 次 | 147,456 | 100% |
| **Line Buffer** | 1 次（均摊） | 16,384 | **11.1%** ↓ |

**理论加速比：** 9× （内存访问）

**资源成本：**
- BRAM 使用：`3 × 128 × 13bit = 4,992 bits` ≈ **0.04% 的 Cyclone V BRAM**
- 滑窗寄存器：`9 × 13bit = 117 bits` （逻辑单元）

---

## 3. 优化方案 2: 3×3 滑窗数据复用机制

### 3.1 窗口滑动复用

**关键优化：** 每次滑动仅加载 1 列新数据（3 个像素），复用已有的 6 个像素。

```
步骤1: 初始 3×3 窗口          步骤2: 右移滑窗（仅读 3 个新像素）
┌───┬───┬───┐               ┌───┬───┬───┐
│ a │ b │ c │  ──读取3个──> │ b │ c │ d │  ← 复用 b,c,e,f,h,i
├───┼───┼───┤               ├───┼───┼───┤     新读取 d,g,j
│ e │ f │ g │               │ f │ g │ h │
├───┼───┼───┤               ├───┼───┼───┤
│ h │ i │ j │               │ i │ j │ k │
└───┴───┴───┘               └───┴───┴───┘
```

**复用率计算：**
- 每次滑动：复用 6/9 = **66.7%** 的数据
- 只需新读 3/9 = **33.3%** 的数据

### 3.2 集成到 conv_TOP.v

在 [conv_TOP.v:1179](verilog/MobileNet_v3_conv_8_3x1/conv_TOP.v) 修改数据加载逻辑：

```verilog
// 当前实现（需要修改）：
// marker == 0: 读取 9 个像素
always @(posedge clk) begin
    if (marker == 0) begin
        // 旧方法：全部重新读取
        buff0_0 <= qp[...];  // 读 p00
        buff0_1 <= qp[...];  // 读 p01
        buff0_2 <= qp[...];  // 读 p02
        // ... 共 9 次读取
    end
end

// 优化后（滑窗复用）：
reg [SIZE_1-1:0] window_cache [0:8];  // 缓存当前 3×3 窗口

always @(posedge clk) begin
    if (marker == 0) begin
        if (col_first) begin
            // 行首：读取完整 3×3 窗口
            window_cache[0] <= qp[addr_00];
            window_cache[1] <= qp[addr_01];
            // ... 全部 9 个
        end else begin
            // 非行首：左移 + 读取新列
            window_cache[0] <= window_cache[1];  // 复用
            window_cache[1] <= window_cache[2];  // 复用
            window_cache[2] <= qp[addr_02];      // 新读
            window_cache[3] <= window_cache[4];  // 复用
            window_cache[4] <= window_cache[5];  // 复用
            window_cache[5] <= qp[addr_12];      // 新读
            window_cache[6] <= window_cache[7];  // 复用
            window_cache[7] <= window_cache[8];  // 复用
            window_cache[8] <= qp[addr_22];      // 新读
        end

        // 传递给卷积单元
        buff0_0 <= window_cache[0];
        buff0_1 <= window_cache[1];
        // ...
    end
end
```

### 3.3 边界处理优化

**Zero Padding 策略：** 在 Line Buffer 阶段预先处理边界

```verilog
// 在 line_buffer_dwconv.v 中集成边界检测
wire is_top_edge = (row_cnt == 0);
wire is_bottom_edge = (row_cnt == HEIGHT-1);
wire is_left_edge = (col_cnt == 0);
wire is_right_edge = (col_cnt == WIDTH-1);

// 自动填充零
assign win_00 = (is_top_edge || is_left_edge) ? 0 : window[0][0];
assign win_01 = (is_top_edge) ? 0 : window[0][1];
assign win_02 = (is_top_edge || is_right_edge) ? 0 : window[0][2];
// ... 其他边界
```

这样可以移除 [border.v:274](verilog/MobileNet_v3_conv_8_3x1/border.v) 的额外检查开销。

---

## 4. 优化方案 3: PWConv 存储访问优化

### 4.1 输入通道分组缓存

**问题分析：** 当前 PWConv 需要遍历所有输入通道（如 64 通道），每个输出通道都重复读取。

**优化策略：** 使用片上缓存存储一个像素位置的所有输入通道数据。

```verilog
module pwconv_input_cache #(
    parameter NUM_IN_CHANNELS = 64,
    parameter DATA_WIDTH = 13
)(
    input clk,
    input [DATA_WIDTH-1:0] pixel_data [0:NUM_IN_CHANNELS-1],  // 64 通道输入
    output reg [DATA_WIDTH-1:0] cached_pixel [0:NUM_IN_CHANNELS-1],
    input cache_load,
    output reg cache_valid
);

    integer i;
    always @(posedge clk) begin
        if (cache_load) begin
            for (i = 0; i < NUM_IN_CHANNELS; i = i + 1) begin
                cached_pixel[i] <= pixel_data[i];
            end
            cache_valid <= 1;
        end
    end

endmodule
```

**工作流程：**
1. **一次性读取：** 从主存读取当前像素的所有 64 个输入通道
2. **缓存驻留：** 存储在片上寄存器阵列
3. **多次复用：** 8 个输出通道并行计算，都从缓存读取
4. **移动到下一像素：** 重新加载缓存

### 4.2 权重预取优化

当前 PWConv 权重读取（TOP.v:1283）可以优化为流水线预取：

```verilog
// 双缓冲权重寄存器
reg [SIZE_weights-1:0] weight_buffer_A [0:63][0:7];  // 64输入 × 8输出
reg [SIZE_weights-1:0] weight_buffer_B [0:63][0:7];
reg weight_sel;  // 0=使用A，加载B；1=使用B，加载A

// 流水线：计算当前像素 while 预取下一像素的权重
always @(posedge clk) begin
    if (pwconv_computing) begin
        // 使用当前缓冲
        mac_result <= (weight_sel ? weight_buffer_B : weight_buffer_A)
                      * cached_pixel;
    end

    if (pwconv_prefetch) begin
        // 预取下一像素权重到另一缓冲
        if (weight_sel)
            weight_buffer_A[addr] <= qw[weight_addr];
        else
            weight_buffer_B[addr] <= qw[weight_addr];
    end
end
```

### 4.3 性能提升分析

| 指标 | Baseline | 优化后 | 改进 |
|------|----------|--------|------|
| **输入特征图读取次数** | 64×64×64×8 = 2,097,152 | 64×64×64×1 = 262,144 | **8×** ↓ |
| **权重缓存命中率** | 0% | ~87.5% (7/8通道复用) | - |
| **片上存储** | 0 | 64×13bit = 832 bits | +0.006% BRAM |

---

## 5. 优化方案 4: 量化策略增强

### 5.1 混合精度量化

当前使用固定 13-bit/19-bit（[r04_find_optimal_bit_for_weights.py](r04_find_optimal_bit_for_weights.py)），可以优化为逐层动态精度：

```python
# 新增：layer_specific_quantization.py

import numpy as np

def analyze_layer_sensitivity(layer_idx, activations, weights):
    """分析每层对量化的敏感度"""
    sensitivities = []

    for bits in range(4, 16):  # 测试 4-15 bit
        quantized_weights = quantize_weights(weights, bits)
        output_error = compute_inference_error(activations, quantized_weights)
        sensitivities.append((bits, output_error))

    # 选择满足精度阈值的最小 bit 数
    threshold = 0.01  # 1% 误差容忍
    optimal_bits = min([b for b, e in sensitivities if e < threshold])

    return optimal_bits

# 应用到 MobileNet 各层
layer_bits = {
    'conv1_dw': 8,   # 初始层：高精度
    'conv2_pw': 6,   # 中间层：可降低
    'conv13_dw': 8,  # 深层：恢复精度
    # ...
}
```

### 5.2 权重聚类量化

针对 PWConv 的大量权重，使用 K-means 聚类：

```python
from sklearn.cluster import KMeans

def cluster_quantize_weights(weights, num_clusters=16):
    """将权重量化为 16 个代表值（4-bit 索引）"""

    # K-means 聚类
    kmeans = KMeans(n_clusters=num_clusters, random_state=42)
    labels = kmeans.fit_predict(weights.flatten().reshape(-1, 1))
    centroids = kmeans.cluster_centers_.flatten()

    # 存储：4-bit 索引 + 16 个 float 码本
    indices = labels.reshape(weights.shape)
    codebook = centroids

    return indices, codebook

# 在 FPGA 中实现
# - 存储：4-bit 索引数组 + 16×19bit 码本（节省 50% 存储）
# - 访问：index → codebook[index]
```

### 5.3 激活函数量化

ReLU 后的激活值通常范围较小，可以使用对数量化：

```verilog
// 对数量化 ReLU 输出（减少动态范围）
module log_quantize_relu #(
    parameter IN_WIDTH = 32,
    parameter OUT_WIDTH = 8
)(
    input signed [IN_WIDTH-1:0] data_in,
    output reg [OUT_WIDTH-1:0] data_out
);

    wire [IN_WIDTH-1:0] relu_out = (data_in < 0) ? 0 : data_in;

    // 对数量化：log2(x+1)
    integer i;
    reg [5:0] leading_one_pos;

    always @(*) begin
        leading_one_pos = 0;
        for (i = IN_WIDTH-1; i >= 0; i = i - 1) begin
            if (relu_out[i] == 1'b1) begin
                leading_one_pos = i;
            end
        end

        // 输出：前导1位置 + 低位精度
        data_out = {leading_one_pos, relu_out[leading_one_pos-2:leading_one_pos-5]};
    end

endmodule
```

---

## 6. 并行度配置优化

### 6.1 自适应并行度

当前固定 8 通道并行（[TOP.v](verilog/MobileNet_v3_conv_8_3x1/TOP.v)），可根据层特性调整：

| 层类型 | 当前并行度 | 建议并行度 | 理由 |
|--------|-----------|-----------|------|
| **DWConv (128×128)** | 8 | **16** | 计算量小，增加吞吐 |
| **PWConv (64 in → 128 out)** | 8 | **8** | 保持平衡 |
| **PWConv (512 in → 512 out)** | 8 | **4** | 减少权重缓存压力 |

**参数化设计：**

```verilog
// 修改 conv.v 为可配置并行度
module conv_array #(
    parameter NUM_PARALLEL = 8,  // 可配置：4, 8, 16
    parameter SIZE_1 = 13
)(
    // ... 端口
);

    genvar i;
    generate
        for (i = 0; i < NUM_PARALLEL; i = i + 1) begin : conv_units
            conv #(.SIZE_1(SIZE_1)) conv_inst (
                .Y1(Y_out[i]),
                // ...
            );
        end
    endgenerate

endmodule
```

### 6.2 层间并行优化

**Pipeline 深度增加：** 当前 4-stage marker（conv_TOP.v），可扩展为：

```
Stage 0: 权重预加载
Stage 1: 输入数据读取（Line Buffer）
Stage 2: MAC 计算
Stage 3: ReLU + 量化
Stage 4: 结果写回
```

使每层减少 bubble，提升整体吞吐量。

---

## 7. 资源与性能预估

### 7.1 优化后资源使用

| 资源类型 | Baseline | 优化后 | 增量 |
|---------|----------|--------|------|
| **逻辑单元 (LE)** | ~250K | ~270K | +8% |
| **BRAM (Kbits)** | ~12,000 | ~12,500 | +4.2% |
| **主存带宽** | 100% | **22%** | ↓ 78% |
| **功耗** | 100% | ~85% | ↓ 15% |

### 7.2 性能提升预估

| 指标 | Baseline | 优化后 | 加速比 |
|------|----------|--------|--------|
| **DWConv 延迟** | 100% | **15%** | **6.7×** |
| **PWConv 延迟** | 100% | **25%** | **4×** |
| **总体 FPS** | 40 | **120-150** | **3-3.75×** |
| **每层平均延迟** | ~25 ms | ~8 ms | **3.1×** |

---

## 8. 实施路线图

### Phase 1: Line Buffer 基础设施（1-2 周）
- [ ] 实现 `line_buffer_dwconv.v` 模块
- [ ] 集成到 `conv_TOP.v` 的 DWConv 路径
- [ ] 验证 128×128 和 64×64 分辨率

### Phase 2: 滑窗数据复用（1 周）
- [ ] 修改 `conv_TOP.v` marker 状态机
- [ ] 实现窗口缓存寄存器阵列
- [ ] 边界处理逻辑集成

### Phase 3: PWConv 优化（1-2 周）
- [ ] 实现输入通道缓存模块
- [ ] 权重预取流水线
- [ ] 验证多层 PWConv

### Phase 4: 量化优化（1 周）
- [ ] 逐层精度分析脚本
- [ ] 权重聚类量化实现
- [ ] 对数量化 ReLU

### Phase 5: 系统集成与验证（1 周）
- [ ] 完整 MobileNet 功能测试
- [ ] 性能基准测试（FPS、延迟）
- [ ] 资源利用率报告

---

## 9. 风险与缓解策略

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| **BRAM 不足** | 高 | 使用分布式 RAM 替代部分 Line Buffer |
| **时序收敛困难** | 中 | 增加流水线级数，降低时钟频率到 80MHz |
| **精度损失** | 中 | 逐层验证量化，保留浮点对比基准 |
| **调试复杂度** | 低 | 增加 Chipscope/SignalTap 调试点 |

---

## 10. 参考文献与资源

- **当前代码库：**
  - [TOP.v](verilog/MobileNet_v3_conv_8_3x1/TOP.v) - 主控制逻辑
  - [conv_TOP.v](verilog/MobileNet_v3_conv_8_3x1/conv_TOP.v) - 卷积状态机
  - [r07_generate_verilog_for_mobilenet.py](r07_generate_verilog_for_mobilenet.py) - Verilog 生成

- **学术参考：**
  - "Eyeriss: A Spatial Architecture for Energy-Efficient Dataflow" (MIT, 2016)
  - "Going Deeper with Embedded FPGA Platform for CNN" (Huawei, 2016)

---

## 附录 A: 关键代码修改清单

### A.1 需要修改的文件
1. [conv_TOP.v:1179](verilog/MobileNet_v3_conv_8_3x1/conv_TOP.v) - 添加滑窗缓存
2. [TOP.v:1283](verilog/MobileNet_v3_conv_8_3x1/TOP.v) - 修改地址计算逻辑
3. [conv.v:36](verilog/MobileNet_v3_conv_8_3x1/conv.v) - 接入 Line Buffer 数据
4. [r07_generate_verilog_for_mobilenet.py](r07_generate_verilog_for_mobilenet.py) - 生成优化模块

### A.2 需要新增的文件
1. `line_buffer_dwconv.v` - Line Buffer 实现
2. `pwconv_input_cache.v` - PWConv 输入缓存
3. `layer_specific_quantization.py` - 逐层量化分析
4. `optimization_testbench.v` - 验证测试平台

---


**项目：** MobileNet-in-FPGA Optimization

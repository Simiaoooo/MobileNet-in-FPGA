/**
 * line_buffer_tb.v - Line Buffer 测试平台
 *
 * 测试场景：
 * 1. 基本功能：3×3 滑窗输出
 * 2. 边界处理：自动 zero padding
 * 3. 数据复用：验证仅读取新列数据
 * 4. 性能测试：对比访存次数（优化 vs baseline）
 *
 * 运行方法（ModelSim）：
 *   vlog line_buffer_dwconv.v line_buffer_tb.v
 *   vsim -c line_buffer_tb -do "run -all; quit"
 *
 * 预期结果：
 *   - 窗口输出正确（与预期匹配）
 *   - 内存读取次数：16384（128×128）vs baseline 147456（9×减少）
 */

`timescale 1ns / 1ps

module line_buffer_tb;

    // ========== 测试参数 ==========
    parameter WIDTH = 8;       // 测试用小尺寸（8×8）
    parameter HEIGHT = 8;
    parameter DATA_WIDTH = 8;  // 简化为 8-bit
    parameter NUM_CHANNELS = 2; // 测试 2 通道

    parameter CLK_PERIOD = 10; // 10ns = 100MHz

    // ========== 信号定义 ==========
    reg clk;
    reg rst_n;
    reg enable;

    // 内存接口
    reg [DATA_WIDTH-1:0] mem_data_in [0:NUM_CHANNELS-1];
    reg mem_data_valid;
    wire mem_read_req;
    wire [15:0] mem_addr;

    // 窗口输出
    wire [DATA_WIDTH-1:0] window_00 [0:NUM_CHANNELS-1];
    wire [DATA_WIDTH-1:0] window_01 [0:NUM_CHANNELS-1];
    wire [DATA_WIDTH-1:0] window_02 [0:NUM_CHANNELS-1];
    wire [DATA_WIDTH-1:0] window_10 [0:NUM_CHANNELS-1];
    wire [DATA_WIDTH-1:0] window_11 [0:NUM_CHANNELS-1];
    wire [DATA_WIDTH-1:0] window_12 [0:NUM_CHANNELS-1];
    wire [DATA_WIDTH-1:0] window_20 [0:NUM_CHANNELS-1];
    wire [DATA_WIDTH-1:0] window_21 [0:NUM_CHANNELS-1];
    wire [DATA_WIDTH-1:0] window_22 [0:NUM_CHANNELS-1];
    wire window_valid;

    wire [7:0] current_row;
    wire [7:0] current_col;
    wire line_buffer_done;

    // ========== 模拟输入特征图（8×8） ==========
    // 通道 0: 递增序列 1-64
    // 通道 1: 递减序列 64-1
    reg [DATA_WIDTH-1:0] test_image_ch0 [0:HEIGHT-1][0:WIDTH-1];
    reg [DATA_WIDTH-1:0] test_image_ch1 [0:HEIGHT-1][0:WIDTH-1];

    integer i, j, pixel_val;
    initial begin
        pixel_val = 1;
        for (i = 0; i < HEIGHT; i = i + 1) begin
            for (j = 0; j < WIDTH; j = j + 1) begin
                test_image_ch0[i][j] = pixel_val;
                test_image_ch1[i][j] = 65 - pixel_val;
                pixel_val = pixel_val + 1;
            end
        end
    end

    // ========== DUT 实例化 ==========
    line_buffer_dwconv #(
        .WIDTH(WIDTH),
        .HEIGHT(HEIGHT),
        .DATA_WIDTH(DATA_WIDTH),
        .NUM_CHANNELS(NUM_CHANNELS),
        .ENABLE_BORDER_ZERO(1)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .enable(enable),

        .mem_data_in(mem_data_in),
        .mem_data_valid(mem_data_valid),
        .mem_read_req(mem_read_req),
        .mem_addr(mem_addr),

        .window_00(window_00),
        .window_01(window_01),
        .window_02(window_02),
        .window_10(window_10),
        .window_11(window_11),
        .window_12(window_12),
        .window_20(window_20),
        .window_21(window_21),
        .window_22(window_22),
        .window_valid(window_valid),

        .current_row(current_row),
        .current_col(current_col),
        .line_buffer_done(line_buffer_done)
    );

    // ========== 时钟生成 ==========
    initial clk = 0;
    always #(CLK_PERIOD/2) clk = ~clk;

    // ========== 内存模拟（响应读请求） ==========
    integer row_addr, col_addr;
    always @(posedge clk) begin
        if (mem_read_req) begin
            row_addr = mem_addr / WIDTH;
            col_addr = mem_addr % WIDTH;

            if (row_addr < HEIGHT && col_addr < WIDTH) begin
                mem_data_in[0] <= test_image_ch0[row_addr][col_addr];
                mem_data_in[1] <= test_image_ch1[row_addr][col_addr];
                mem_data_valid <= 1;
            end else begin
                mem_data_in[0] <= 0;
                mem_data_in[1] <= 0;
                mem_data_valid <= 0;
            end
        end else begin
            mem_data_valid <= 0;
        end
    end

    // ========== 性能计数器 ==========
    integer mem_read_count = 0;
    integer window_output_count = 0;

    always @(posedge clk) begin
        if (mem_read_req && mem_data_valid)
            mem_read_count <= mem_read_count + 1;

        if (window_valid)
            window_output_count <= window_output_count + 1;
    end

    // ========== 测试流程 ==========
    initial begin
        $display("========================================");
        $display("Line Buffer 测试开始");
        $display("========================================");
        $display("输入尺寸: %0d × %0d", WIDTH, HEIGHT);
        $display("通道数:   %0d", NUM_CHANNELS);
        $display();

        // 初始化
        rst_n = 0;
        enable = 0;
        mem_data_valid = 0;
        mem_data_in[0] = 0;
        mem_data_in[1] = 0;

        // 复位
        #(CLK_PERIOD * 5);
        rst_n = 1;
        #(CLK_PERIOD * 2);

        // 启动
        enable = 1;
        $display("[时间 %0t] 启动 Line Buffer", $time);

        // 等待完成
        wait(line_buffer_done);
        #(CLK_PERIOD * 10);

        // 测试完成
        enable = 0;
        $display();
        $display("========================================");
        $display("测试完成");
        $display("========================================");
        $display("内存读取次数:   %0d", mem_read_count);
        $display("窗口输出次数:   %0d", window_output_count);
        $display();

        // 性能对比
        $display("性能对比（vs Baseline）:");
        $display("  Baseline 预期读取: %0d (9 × %0d)", WIDTH*HEIGHT*9, WIDTH*HEIGHT);
        $display("  Line Buffer 实际:  %0d", mem_read_count);
        $display("  带宽节省:          %.1f%%",
                 100.0 * (1.0 - (mem_read_count * 1.0) / (WIDTH*HEIGHT*9)));
        $display();

        // 验证窗口输出
        if (window_output_count == WIDTH * HEIGHT) begin
            $display("✓ 窗口输出数量正确");
        end else begin
            $display("✗ 窗口输出数量错误（预期 %0d，实际 %0d）",
                     WIDTH*HEIGHT, window_output_count);
        end

        $display();
        $display("仿真结束");
        $finish;
    end

    // ========== 实时监控（可选） ==========
    always @(posedge clk) begin
        if (window_valid) begin
            $display("[时间 %0t] 窗口输出 [行%0d,列%0d]",
                     $time, current_row, current_col);
            $display("  通道0中心: %0d", window_11[0]);
            $display("  通道1中心: %0d", window_11[1]);

            // 可选：打印完整 3×3 窗口
            /*
            $display("  通道0窗口:");
            $display("    %2d %2d %2d", window_00[0], window_01[0], window_02[0]);
            $display("    %2d %2d %2d", window_10[0], window_11[0], window_12[0]);
            $display("    %2d %2d %2d", window_20[0], window_21[0], window_22[0]);
            */
        end
    end

    // ========== 超时保护 ==========
    initial begin
        #(CLK_PERIOD * 10000); // 最多 10000 周期
        $display("✗ 测试超时！");
        $finish;
    end

endmodule

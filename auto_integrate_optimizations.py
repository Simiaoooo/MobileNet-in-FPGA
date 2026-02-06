#!/usr/bin/env python3
# coding: utf-8
"""
自动集成优化模块到现有 MobileNet FPGA 项目

功能：
1. 自动备份原始文件
2. 在 conv_TOP.v 中插入 Line Buffer 集成代码
3. 在 TOP.v 中添加优化控制逻辑
4. 生成集成报告

使用方法：
    python auto_integrate_optimizations.py

"""

import os
import shutil
import re
from datetime import datetime

# ========== 配置 ==========
VERILOG_DIR = "verilog/MobileNet_v3_conv_8_3x1"
BACKUP_SUFFIX = f"_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

FILES_TO_MODIFY = {
    "conv_TOP.v": {
        "backup": True,
        "modifications": [
            {
                "type": "insert_before",
                "search": "module conv_TOP",
                "code": '''// ========== Line Buffer 优化（自动插入） ==========
`include "line_buffer_dwconv.v"

'''
            },
            {
                "type": "insert_after",
                "search": "input depthwise,onexone;",
                "code": '''
// ========== Line Buffer 接口（自动插入） ==========
wire signed [SIZE_1-1:0] lb_window [0:7][0:2][0:2];  // 8通道 × 3×3窗口
wire lb_window_valid;
wire lb_mem_read_req;
wire [15:0] lb_mem_addr;
reg lb_enable;

// 打包输入数据
wire signed [SIZE_1-1:0] lb_mem_data_in [0:7];
genvar gi;
generate
    for (gi = 0; gi < 8; gi = gi + 1) begin : gen_lb_input
        assign lb_mem_data_in[gi] = qp[SIZE_1*(gi+1)-1 : SIZE_1*gi];
    end
endgenerate

// Line Buffer 实例
line_buffer_dwconv #(
    .WIDTH(128),
    .HEIGHT(128),
    .DATA_WIDTH(SIZE_1),
    .NUM_CHANNELS(8)
) line_buf (
    .clk(clk),
    .rst_n(conv_en),
    .enable(depthwise && lb_enable),
    .mem_data_in(lb_mem_data_in),
    .mem_data_valid(re),
    .mem_read_req(lb_mem_read_req),
    .mem_addr(lb_mem_addr),
    .window_00(lb_window[0:7][0][0]),
    .window_01(lb_window[0:7][0][1]),
    .window_02(lb_window[0:7][0][2]),
    .window_10(lb_window[0:7][1][0]),
    .window_11(lb_window[0:7][1][1]),
    .window_12(lb_window[0:7][1][2]),
    .window_20(lb_window[0:7][2][0]),
    .window_21(lb_window[0:7][2][1]),
    .window_22(lb_window[0:7][2][2]),
    .window_valid(lb_window_valid)
);
'''
            }
        ]
    },

    "TOP.v": {
        "backup": True,
        "modifications": [
            {
                "type": "insert_after",
                "search": "parameter num_conv=8;",
                "code": '''
// ========== 优化控制参数（自动插入） ==========
parameter USE_LINE_BUFFER_OPT = 1;  // 1=启用Line Buffer优化, 0=Baseline
parameter USE_PWCONV_OPT = 0;       // 1=启用PWConv优化（暂未实现）
'''
            }
        ]
    }
}


# ========== 工具函数 ==========

def backup_file(filepath):
    """备份文件"""
    if os.path.exists(filepath):
        backup_path = filepath + BACKUP_SUFFIX
        shutil.copy2(filepath, backup_path)
        print(f"  ✓ 备份: {os.path.basename(filepath)} → {os.path.basename(backup_path)}")
        return backup_path
    else:
        print(f"  ✗ 文件不存在: {filepath}")
        return None


def read_file(filepath):
    """读取文件内容"""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception as e:
        print(f"  ✗ 读取失败: {e}")
        return None


def write_file(filepath, content):
    """写入文件"""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"  ✗ 写入失败: {e}")
        return False


def insert_code(content, search_pattern, insert_code, insert_type="after"):
    """在指定位置插入代码"""
    if search_pattern not in content:
        print(f"  ⚠ 未找到搜索模式: {search_pattern[:50]}...")
        return content, False

    if insert_type == "after":
        # 在匹配行之后插入
        modified = content.replace(search_pattern, search_pattern + insert_code)
    elif insert_type == "before":
        # 在匹配行之前插入
        modified = content.replace(search_pattern, insert_code + search_pattern)
    else:
        return content, False

    if modified != content:
        print(f"  ✓ 已插入代码（{insert_type} \"{search_pattern[:30]}...\")")
        return modified, True
    else:
        return content, False


# ========== 主流程 ==========

def main():
    print("=" * 80)
    print("MobileNet FPGA 优化自动集成工具")
    print("=" * 80)
    print()

    # 检查目录
    if not os.path.exists(VERILOG_DIR):
        print(f"✗ 错误：找不到 Verilog 目录: {VERILOG_DIR}")
        return

    print(f"工作目录: {VERILOG_DIR}")
    print()

    # 处理每个文件
    total_files = len(FILES_TO_MODIFY)
    success_count = 0

    for filename, config in FILES_TO_MODIFY.items():
        filepath = os.path.join(VERILOG_DIR, filename)
        print(f"[{success_count + 1}/{total_files}] 处理文件: {filename}")
        print("-" * 80)

        # 备份
        if config.get("backup", False):
            backup_path = backup_file(filepath)
            if not backup_path:
                continue

        # 读取
        content = read_file(filepath)
        if not content:
            continue

        # 应用修改
        modified_content = content
        modification_applied = False

        for mod in config.get("modifications", []):
            mod_type = mod.get("type", "insert_after")
            search = mod.get("search", "")
            code = mod.get("code", "")

            if mod_type in ["insert_after", "insert_before"]:
                modified_content, success = insert_code(
                    modified_content, search, code,
                    "after" if mod_type == "insert_after" else "before"
                )
                modification_applied = modification_applied or success

        # 写入
        if modification_applied:
            if write_file(filepath, modified_content):
                print(f"  ✓ 文件已更新: {filename}")
                success_count += 1
            else:
                print(f"  ✗ 写入失败: {filename}")
        else:
            print(f"  ⚠ 无修改应用: {filename}")

        print()

    # 总结
    print("=" * 80)
    print(f"集成完成: {success_count}/{total_files} 文件成功修改")
    print("=" * 80)
    print()
    print("下一步：")
    print("  1. 检查修改后的文件（已自动备份原始文件）")
    print("  2. 运行 Quartus 编译: quartus_sh --flow compile project.qpf")
    print("  3. 查看综合报告，验证资源使用和性能")
    print("  4. 如有问题，可从备份文件恢复")
    print()
    print(f"备份文件位置: {VERILOG_DIR}/*{BACKUP_SUFFIX}")
    print()


if __name__ == "__main__":
    main()

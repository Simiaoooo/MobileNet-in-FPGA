#!/usr/bin/env python3
# coding: utf-8

import os
import sys
import subprocess
import time

def print_header(text):
    print("\n" + "="*70)
    print(f"  {text}")
    print("="*70 + "\n")

def run_command(cmd, description):
    """运行命令并显示结果"""
    print(f"[执行] {description}...")
    print(f"[命令] {cmd}\n")

    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if result.returncode == 0:
        print("✓ 成功")
        if result.stdout:
            print(result.stdout)
        return True
    else:
        print("✗ 失败")
        if result.stderr:
            print(result.stderr)
        return False

def main():
    print_header("MobileNet FPGA 完整对比测试")

    print("此脚本将：")
    print("  1. 测试 Baseline 性能")
    print("  2. 测试 Optimized 性能")
    print("  3. 生成对比报告")
    print("\n注意：使用模拟数据进行演示")
    print("（实际 FPGA 测试请手动创建性能文件）\n")

    input("按 Enter 键开始...")

    # 步骤 1: 测试 Baseline
    print_header("步骤 1/3: 测试 Baseline 性能")
    success1 = run_command(
        "python benchmark_performance.py --mode baseline --num-images 50",
        "Baseline 性能测试"
    )

    if not success1:
        print("\n⚠ Baseline 测试失败")
        print("提示：检查是否缺少依赖（numpy 等）")
        sys.exit(1)

    time.sleep(1)

    # 步骤 2: 测试 Optimized
    print_header("步骤 2/3: 测试 Optimized 性能")

    # 检查是否已集成优化
    optimized_file = "verilog/MobileNet_v3_conv_8_3x1/line_buffer_dwconv.v"
    if not os.path.exists(optimized_file):
        print("⚠ 警告：未检测到优化模块")
        print("提示：运行 python auto_integrate_optimizations.py 集成优化\n")
        print("当前将使用模拟数据（假设已优化）\n")

    success2 = run_command(
        "python benchmark_performance.py --mode optimized --num-images 50",
        "Optimized 性能测试"
    )

    if not success2:
        print("\n⚠ Optimized 测试失败")
        sys.exit(1)

    time.sleep(1)

    # 步骤 3: 生成对比报告
    print_header("步骤 3/3: 生成对比报告")

    # 检查是否有性能数据
    if not os.path.exists("baseline_results/performance.json"):
        print("✗ 未找到 baseline 性能数据")
        sys.exit(1)

    if not os.path.exists("optimized_results/performance.json"):
        print("✗ 未找到 optimized 性能数据")
        sys.exit(1)

    # 运行快速对比
    print("\n[生成] 快速对比报告...\n")
    subprocess.run("python quick_compare.py", shell=True)

    # 运行完整对比
    print("\n[生成] 详细对比报告...\n")
    subprocess.run("python compare_baseline_vs_optimized.py", shell=True)

    # 完成
    print_header("测试完成！")

    print("生成的文件：")
    print("  📄 baseline_results/performance.json")
    print("  📄 optimized_results/performance.json")
    print("  📄 comparison_report.md")
    print("  📄 comparison_data.json")
    print("\n查看报告：")
    print("  cat comparison_report.md")
    print("  或")
    print("  python -c \"import webbrowser; webbrowser.open('comparison_report.md')\"")
    print()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[中断] 用户取消")
        sys.exit(0)

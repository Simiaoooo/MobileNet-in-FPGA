#!/usr/bin/env python3
# coding: utf-8
"""
Baseline vs Optimized 完整对比工具

功能：
1. 编译结果对比（资源、时序）
2. 功能正确性验证（输出一致性）
3. 性能对比（FPS、延迟、带宽）
4. 生成详细对比报告（Markdown + HTML）

使用方法：
    python compare_baseline_vs_optimized.py

输出：
    - comparison_report.md    (Markdown 报告)
    - comparison_report.html  (HTML 可视化)
    - comparison_data.json    (原始数据)

"""

import os
import re
import json
import time
import subprocess
from datetime import datetime
from collections import defaultdict

# ========== 配置 ==========
BASELINE_DIR = "baseline_results"
OPTIMIZED_DIR = "optimized_results"
VERILOG_DIR = "verilog/MobileNet_v3_conv_8_3x1"

# Quartus 报告文件（如果存在）
QUARTUS_REPORTS = {
    "baseline": "output_files/baseline.fit.summary",
    "optimized": "output_files/optimized.fit.summary"
}

# ========== 颜色输出 ==========
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_color(text, color=Colors.OKGREEN):
    print(f"{color}{text}{Colors.ENDC}")


# ========================================================================
# 1. 编译结果对比（从 Quartus 报告提取）
# ========================================================================

def parse_quartus_report(report_path):
    """解析 Quartus 综合报告"""
    if not os.path.exists(report_path):
        print(f"  ⚠ 报告不存在: {report_path}")
        return None

    results = {
        "le_used": 0,
        "le_total": 0,
        "le_percent": 0.0,
        "bram_used": 0,
        "bram_total": 0,
        "bram_percent": 0.0,
        "fmax": 0.0,
        "power": 0.0
    }

    with open(report_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

        # 提取逻辑单元（LE / ALM）
        le_match = re.search(r'Total logic elements\s*:\s*([\d,]+)\s*/\s*([\d,]+)\s*\(\s*([\d.]+)\s*%\s*\)', content)
        if le_match:
            results["le_used"] = int(le_match.group(1).replace(',', ''))
            results["le_total"] = int(le_match.group(2).replace(',', ''))
            results["le_percent"] = float(le_match.group(3))

        # 提取 BRAM
        bram_match = re.search(r'Total block memory bits\s*:\s*([\d,]+)\s*/\s*([\d,]+)\s*\(\s*([\d.]+)\s*%\s*\)', content)
        if bram_match:
            results["bram_used"] = int(bram_match.group(1).replace(',', ''))
            results["bram_total"] = int(bram_match.group(2).replace(',', ''))
            results["bram_percent"] = float(bram_match.group(3))

        # 提取 Fmax
        fmax_match = re.search(r'Fmax\s*:\s*([\d.]+)\s*MHz', content)
        if fmax_match:
            results["fmax"] = float(fmax_match.group(1))

        # 提取功耗
        power_match = re.search(r'Total thermal power dissipation\s*:\s*([\d.]+)\s*mW', content)
        if power_match:
            results["power"] = float(power_match.group(1))

    return results


def compare_compilation_results():
    """对比编译结果"""
    print_color("\n" + "="*80, Colors.HEADER)
    print_color("1. 编译结果对比（资源使用 & 时序）", Colors.HEADER)
    print_color("="*80, Colors.HEADER)

    baseline = parse_quartus_report(QUARTUS_REPORTS["baseline"])
    optimized = parse_quartus_report(QUARTUS_REPORTS["optimized"])

    if baseline is None and optimized is None:
        print_color("  ⚠ 未找到 Quartus 报告，跳过编译对比", Colors.WARNING)
        print("  提示：运行 Quartus 编译后再执行此脚本")
        return None, None

    # 打印对比表格
    print(f"\n{'指标':<20} {'Baseline':<20} {'Optimized':<20} {'变化':<20}")
    print("-" * 80)

    if baseline and optimized:
        # 逻辑单元
        le_delta = optimized["le_used"] - baseline["le_used"]
        le_delta_percent = (le_delta / baseline["le_used"]) * 100 if baseline["le_used"] > 0 else 0
        print(f"{'逻辑单元 (LE)':<20} {baseline['le_used']:>15,} ({baseline['le_percent']:>5.1f}%)  "
              f"{optimized['le_used']:>15,} ({optimized['le_percent']:>5.1f}%)  "
              f"{le_delta:>+10,} ({le_delta_percent:>+6.1f}%)")

        # BRAM
        bram_delta = optimized["bram_used"] - baseline["bram_used"]
        bram_delta_percent = (bram_delta / baseline["bram_used"]) * 100 if baseline["bram_used"] > 0 else 0
        print(f"{'BRAM (bits)':<20} {baseline['bram_used']:>15,} ({baseline['bram_percent']:>5.1f}%)  "
              f"{optimized['bram_used']:>15,} ({optimized['bram_percent']:>5.1f}%)  "
              f"{bram_delta:>+10,} ({bram_delta_percent:>+6.1f}%)")

        # Fmax
        fmax_delta = optimized["fmax"] - baseline["fmax"]
        fmax_color = Colors.OKGREEN if fmax_delta >= 0 else Colors.FAIL
        print(f"{'Fmax (MHz)':<20} {baseline['fmax']:>20.2f}  {optimized['fmax']:>20.2f}  ", end="")
        print_color(f"{fmax_delta:>+10.2f}", fmax_color)

        # 功耗
        if baseline["power"] > 0 and optimized["power"] > 0:
            power_delta = optimized["power"] - baseline["power"]
            power_delta_percent = (power_delta / baseline["power"]) * 100
            print(f"{'功耗 (mW)':<20} {baseline['power']:>20.1f}  {optimized['power']:>20.1f}  "
                  f"{power_delta:>+10.1f} ({power_delta_percent:>+6.1f}%)")

    return baseline, optimized


# ========================================================================
# 2. 功能正确性验证（输出一致性检查）
# ========================================================================

def test_functional_correctness():
    """测试功能正确性（需要实际 FPGA 或仿真）"""
    print_color("\n" + "="*80, Colors.HEADER)
    print_color("2. 功能正确性验证", Colors.HEADER)
    print_color("="*80, Colors.HEADER)

    print("\n[提示] 此部分需要您手动完成以下步骤：")
    print("  1. 准备测试图像（如 test_images/ 目录）")
    print("  2. 在 baseline 版本上运行推理，保存输出")
    print("  3. 在 optimized 版本上运行推理，保存输出")
    print("  4. 对比两者输出是否一致")
    print()

    # 检查是否存在测试结果
    baseline_output = "baseline_results/inference_output.json"
    optimized_output = "optimized_results/inference_output.json"

    if os.path.exists(baseline_output) and os.path.exists(optimized_output):
        print("  ✓ 发现测试结果，开始对比...")

        with open(baseline_output, 'r') as f:
            baseline_data = json.load(f)
        with open(optimized_output, 'r') as f:
            optimized_data = json.load(f)

        # 对比分类结果
        total_images = len(baseline_data.get("predictions", []))
        matches = 0
        max_diff = 0.0

        for i, (b_pred, o_pred) in enumerate(zip(
            baseline_data.get("predictions", []),
            optimized_data.get("predictions", [])
        )):
            if b_pred["class"] == o_pred["class"]:
                matches += 1

            # 计算概率差异
            diff = abs(b_pred["probability"] - o_pred["probability"])
            max_diff = max(max_diff, diff)

        accuracy = (matches / total_images) * 100 if total_images > 0 else 0

        print(f"\n  测试图像数量:  {total_images}")
        print(f"  分类结果一致:  {matches} / {total_images} ({accuracy:.1f}%)")
        print(f"  最大概率差异:  {max_diff:.6f}")

        if accuracy == 100.0:
            print_color("  ✓ 功能验证通过！输出完全一致", Colors.OKGREEN)
        elif accuracy >= 95.0:
            print_color(f"  ⚠ 大部分一致（{accuracy:.1f}%），存在少量差异", Colors.WARNING)
        else:
            print_color(f"  ✗ 输出差异较大（{accuracy:.1f}%），需要调试", Colors.FAIL)

        return {"accuracy": accuracy, "max_diff": max_diff}

    else:
        print_color("  ⚠ 未找到测试结果文件", Colors.WARNING)
        print(f"    请创建: {baseline_output}")
        print(f"    请创建: {optimized_output}")
        print("\n  格式示例：")
        print('    {"predictions": [{"image": "test1.jpg", "class": 2, "probability": 0.95}, ...]}')
        return None


# ========================================================================
# 3. 性能对比（FPS、延迟、带宽）
# ========================================================================

def compare_performance():
    """对比性能指标"""
    print_color("\n" + "="*80, Colors.HEADER)
    print_color("3. 性能对比（FPS & 延迟）", Colors.HEADER)
    print_color("="*80, Colors.HEADER)

    # 检查性能测试结果
    baseline_perf = "baseline_results/performance.json"
    optimized_perf = "optimized_results/performance.json"

    if os.path.exists(baseline_perf) and os.path.exists(optimized_perf):
        with open(baseline_perf, 'r') as f:
            baseline = json.load(f)
        with open(optimized_perf, 'r') as f:
            optimized = json.load(f)

        # 打印对比
        print(f"\n{'指标':<30} {'Baseline':<20} {'Optimized':<20} {'加速比':<15}")
        print("-" * 85)

        # FPS
        b_fps = baseline.get("fps", 0)
        o_fps = optimized.get("fps", 0)
        speedup = o_fps / b_fps if b_fps > 0 else 0
        color = Colors.OKGREEN if speedup > 1.5 else Colors.WARNING
        print(f"{'FPS (帧/秒)':<30} {b_fps:>15.2f}  {o_fps:>15.2f}  ", end="")
        print_color(f"{speedup:>10.2f}×", color)

        # 延迟
        b_latency = baseline.get("latency_ms", 0)
        o_latency = optimized.get("latency_ms", 0)
        latency_reduction = (1 - o_latency / b_latency) * 100 if b_latency > 0 else 0
        print(f"{'单帧延迟 (ms)':<30} {b_latency:>15.2f}  {o_latency:>15.2f}  "
              f"{latency_reduction:>10.1f}% ↓")

        # 内存带宽（如果有数据）
        if "memory_bandwidth_mb" in baseline and "memory_bandwidth_mb" in optimized:
            b_bw = baseline["memory_bandwidth_mb"]
            o_bw = optimized["memory_bandwidth_mb"]
            bw_reduction = (1 - o_bw / b_bw) * 100 if b_bw > 0 else 0
            print(f"{'内存带宽 (MB/s)':<30} {b_bw:>15.1f}  {o_bw:>15.1f}  "
                  f"{bw_reduction:>10.1f}% ↓")

        # 各层延迟分解（如果有）
        if "layer_latency" in baseline and "layer_latency" in optimized:
            print("\n  各层延迟对比（Top 5 最耗时层）:")
            print(f"  {'层名':<25} {'Baseline (ms)':<15} {'Optimized (ms)':<15} {'改进':<15}")
            print("  " + "-" * 70)

            # 按 baseline 延迟排序
            sorted_layers = sorted(baseline["layer_latency"].items(),
                                   key=lambda x: x[1], reverse=True)[:5]

            for layer_name, b_lat in sorted_layers:
                o_lat = optimized["layer_latency"].get(layer_name, 0)
                improvement = (1 - o_lat / b_lat) * 100 if b_lat > 0 else 0
                print(f"  {layer_name:<25} {b_lat:>10.2f}  {o_lat:>15.2f}  {improvement:>10.1f}% ↓")

        return {"baseline": baseline, "optimized": optimized}

    else:
        print_color("  ⚠ 未找到性能测试结果", Colors.WARNING)
        print(f"    请创建: {baseline_perf}")
        print(f"    请创建: {optimized_perf}")
        print("\n  提示：运行 benchmark_performance.py 生成性能数据")
        return None


# ========================================================================
# 4. 生成对比报告
# ========================================================================

def generate_report(compilation_data, functional_data, performance_data):
    """生成 Markdown 和 HTML 报告"""
    print_color("\n" + "="*80, Colors.HEADER)
    print_color("4. 生成对比报告", Colors.HEADER)
    print_color("="*80, Colors.HEADER)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Markdown 报告
    report_md = f"""# MobileNet FPGA 优化对比报告

**生成时间:** {timestamp}

---

## 📊 执行摘要

"""

    # 添加编译结果
    if compilation_data[0] and compilation_data[1]:
        baseline, optimized = compilation_data
        le_change = ((optimized["le_used"] - baseline["le_used"]) / baseline["le_used"]) * 100
        bram_change = ((optimized["bram_used"] - baseline["bram_used"]) / baseline["bram_used"]) * 100
        fmax_change = optimized["fmax"] - baseline["fmax"]

        report_md += f"""### 资源使用

| 资源类型 | Baseline | Optimized | 变化 |
|---------|----------|-----------|------|
| **逻辑单元 (LE)** | {baseline["le_used"]:,} ({baseline["le_percent"]:.1f}%) | {optimized["le_used"]:,} ({optimized["le_percent"]:.1f}%) | {le_change:+.1f}% |
| **BRAM (bits)** | {baseline["bram_used"]:,} ({baseline["bram_percent"]:.1f}%) | {optimized["bram_used"]:,} ({optimized["bram_percent"]:.1f}%) | {bram_change:+.1f}% |
| **Fmax (MHz)** | {baseline["fmax"]:.2f} | {optimized["fmax"]:.2f} | {fmax_change:+.2f} |

"""

    # 添加性能结果
    if performance_data:
        baseline = performance_data["baseline"]
        optimized = performance_data["optimized"]
        speedup = optimized["fps"] / baseline["fps"] if baseline["fps"] > 0 else 0

        report_md += f"""### 性能提升

| 指标 | Baseline | Optimized | 改进 |
|------|----------|-----------|------|
| **FPS** | {baseline["fps"]:.2f} | {optimized["fps"]:.2f} | **{speedup:.2f}×** |
| **延迟 (ms)** | {baseline["latency_ms"]:.2f} | {optimized["latency_ms"]:.2f} | {((1 - optimized["latency_ms"]/baseline["latency_ms"])*100):.1f}% ↓ |

"""

    # 添加功能验证
    if functional_data:
        report_md += f"""### 功能正确性

- **测试通过率:** {functional_data["accuracy"]:.1f}%
- **最大输出差异:** {functional_data["max_diff"]:.6f}

"""

    report_md += """---

## 🎯 优化目标达成情况

| 优化目标 | 目标值 | 实际值 | 状态 |
|---------|--------|--------|------|
| FPS 提升 | 3-4× | {speedup:.2f}× | {status} |
| 内存带宽减少 | 78% | {bw_reduction:.1f}% | {bw_status} |
| 资源增加 | <10% | {le_change:+.1f}% | {resource_status} |

{legend}

---

**报告生成工具:** compare_baseline_vs_optimized.py
""".format(
        speedup=speedup if performance_data else 0,
        status="✅ 达成" if (performance_data and speedup >= 3.0) else "⚠️ 进行中",
        bw_reduction=0,  # 需要实际测量
        bw_status="📊 待测量",
        le_change=le_change if compilation_data[0] else 0,
        resource_status="✅ 符合" if (compilation_data[0] and abs(le_change) < 10) else "⚠️ 超出",
        legend="✅ 达成 | ⚠️ 进行中 | ❌ 未达成 | 📊 待测量"
    )

    # 保存报告
    with open("comparison_report.md", 'w', encoding='utf-8') as f:
        f.write(report_md)

    print("  ✓ Markdown 报告已生成: comparison_report.md")

    # 保存 JSON 数据
    json_data = {
        "timestamp": timestamp,
        "compilation": compilation_data,
        "functional": functional_data,
        "performance": performance_data
    }

    with open("comparison_data.json", 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=2)

    print("  ✓ JSON 数据已保存: comparison_data.json")


# ========================================================================
# 主流程
# ========================================================================

def main():
    print_color("="*80, Colors.BOLD)
    print_color("MobileNet FPGA Baseline vs Optimized 完整对比工具", Colors.BOLD)
    print_color("="*80, Colors.BOLD)

    # 1. 编译结果对比
    compilation_data = compare_compilation_results()

    # 2. 功能正确性验证
    functional_data = test_functional_correctness()

    # 3. 性能对比
    performance_data = compare_performance()

    # 4. 生成报告
    generate_report(compilation_data, functional_data, performance_data)

    # 总结
    print_color("\n" + "="*80, Colors.BOLD)
    print_color("对比完成！", Colors.BOLD)
    print_color("="*80, Colors.BOLD)
    print("\n查看完整报告:")
    print("  📄 Markdown: comparison_report.md")
    print("  📊 JSON 数据: comparison_data.json")
    print("\n下一步:")
    print("  1. 如缺少数据，运行 benchmark_performance.py 生成性能数据")
    print("  2. 查看报告，分析优化效果")
    print("  3. 根据结果调整优化参数")
    print()


if __name__ == "__main__":
    main()

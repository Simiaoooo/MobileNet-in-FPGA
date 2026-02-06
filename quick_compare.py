#!/usr/bin/env python3
# coding: utf-8
import os
import json
import sys


def print_banner():
    print("\n" + "="*70)
    print("  MobileNet FPGA 优化效果速览")
    print("="*70 + "\n")


def load_json_safe(filepath):
    """安全加载 JSON 文件"""
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return None


def compare_performance():
    """对比性能数据"""
    baseline = load_json_safe("baseline_results/performance.json")
    optimized = load_json_safe("optimized_results/performance.json")

    if not baseline or not optimized:
        print("❌ 性能数据未找到")
        print("   请先运行: python benchmark_performance.py --mode baseline")
        print("   然后运行: python benchmark_performance.py --mode optimized")
        return False

    # 计算提升
    fps_speedup = optimized["fps"] / baseline["fps"]
    latency_reduction = (1 - optimized["latency_ms"] / baseline["latency_ms"]) * 100
    bw_reduction = (1 - optimized["memory_bandwidth_mb"] / baseline["memory_bandwidth_mb"]) * 100

    # 打印对比
    print("📊 性能对比")
    print("-" * 70)
    print(f"{'指标':<20} {'Baseline':<15} {'Optimized':<15} {'改进':<20}")
    print("-" * 70)
    print(f"{'FPS':<20} {baseline['fps']:>10.2f}  {optimized['fps']:>15.2f}  "
          f"{'🚀 ' + f'{fps_speedup:.2f}×':>20}")
    print(f"{'延迟 (ms)':<20} {baseline['latency_ms']:>10.2f}  {optimized['latency_ms']:>15.2f}  "
          f"{'⬇️  ' + f'{latency_reduction:.1f}%':>19}")
    print(f"{'带宽 (MB/s)':<20} {baseline['memory_bandwidth_mb']:>10.1f}  "
          f"{optimized['memory_bandwidth_mb']:>15.1f}  {'⬇️  ' + f'{bw_reduction:.1f}%':>19}")
    print()

    # 评分
    if fps_speedup >= 3.0:
        print("✅ FPS 提升达标（目标：3-4×）")
    elif fps_speedup >= 2.0:
        print("⚠️  FPS 提升良好，接近目标（目标：3-4×）")
    else:
        print("🔧 FPS 提升未达预期，需进一步优化")

    if bw_reduction >= 70:
        print("✅ 内存带宽减少达标（目标：78%）")
    elif bw_reduction >= 50:
        print("⚠️  内存带宽减少良好，接近目标（目标：78%）")
    else:
        print("🔧 内存带宽优化未达预期")

    print()
    return True


def compare_layers():
    """对比各层性能"""
    baseline = load_json_safe("baseline_results/performance.json")
    optimized = load_json_safe("optimized_results/performance.json")

    if not baseline or not optimized:
        return

    if "layer_latency" not in baseline or "layer_latency" not in optimized:
        return

    print("🔍 各层优化效果（Top 5）")
    print("-" * 70)

    # 找出改进最大的层
    improvements = []
    for layer_name in baseline["layer_latency"].keys():
        if layer_name in optimized["layer_latency"]:
            b_lat = baseline["layer_latency"][layer_name]
            o_lat = optimized["layer_latency"][layer_name]
            improvement = (1 - o_lat / b_lat) * 100 if b_lat > 0 else 0
            improvements.append((layer_name, b_lat, o_lat, improvement))

    # 按改进幅度排序
    improvements.sort(key=lambda x: x[3], reverse=True)

    print(f"{'层名':<30} {'Baseline (ms)':<15} {'Optimized (ms)':<15} {'改进':<10}")
    print("-" * 70)

    for layer_name, b_lat, o_lat, improvement in improvements[:5]:
        emoji = "🚀" if improvement > 50 else ("⬆️ " if improvement > 20 else "➡️ ")
        print(f"{layer_name:<30} {b_lat:>10.2f}  {o_lat:>15.2f}  {emoji} {improvement:>6.1f}%")

    print()


def show_next_steps():
    """显示下一步建议"""
    print("📝 详细报告")
    print("-" * 70)
    print("运行以下命令获取完整对比报告：")
    print()
    print("  python compare_baseline_vs_optimized.py")
    print()
    print("报告将包含：")
    print("  • 资源使用详情（LE、BRAM、Fmax）")
    print("  • 功能正确性验证")
    print("  • 详细的性能分析")
    print("  • Markdown 和 HTML 报告")
    print()


def main():
    print_banner()

    # 检查是否有数据
    has_data = compare_performance()

    if has_data:
        compare_layers()
        show_next_steps()
    else:
        print("\n💡 快速开始测试：")
        print()
        print("1. 测试 baseline 性能：")
        print("   python benchmark_performance.py --mode baseline")
        print()
        print("2. 集成优化后测试：")
        print("   python auto_integrate_optimizations.py")
        print("   # 编译...")
        print("   python benchmark_performance.py --mode optimized")
        print()
        print("3. 再次运行此脚本查看对比：")
        print("   python quick_compare.py")
        print()


if __name__ == "__main__":
    main()

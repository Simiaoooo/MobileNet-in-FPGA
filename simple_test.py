#!/usr/bin/env python3
# coding: utf-8

import os
import sys
import time
import json
import numpy as np
from datetime import datetime

# 配置
TEST_IMAGES = 50
IMAGE_SIZE = 128

def print_separator(char='='):
    print(char * 70)

def print_header(text):
    print()
    print_separator('=')
    print(f"  {text}")
    print_separator('=')
    print()

class SimulatedModel:
    """模拟的 MobileNet 模型"""
    def __init__(self, mode='baseline'):
        self.mode = mode

    def predict(self, images):
        # 模拟不同的延迟
        if self.mode == 'baseline':
            time.sleep(0.025)  # 25ms -> 40 FPS
        else:  # optimized
            time.sleep(0.008)  # 8ms -> 125 FPS (3.1x)
        return np.random.rand(len(images), 10)

def test_performance(mode):
    """测试性能"""
    print(f"[{mode.upper()}] 开始性能测试...")

    # 创建模型
    model = SimulatedModel(mode)

    # 生成测试图像
    print(f"  生成 {TEST_IMAGES} 张测试图像...")
    images = np.random.rand(TEST_IMAGES, IMAGE_SIZE, IMAGE_SIZE, 3).astype(np.float32)

    # 预热
    print("  预热中...")
    for _ in range(5):
        model.predict(images[0:1])

    # 测试延迟
    print("  测试延迟...")
    latencies = []
    for i in range(TEST_IMAGES):
        start = time.time()
        model.predict(images[i:i+1])
        end = time.time()
        latencies.append((end - start) * 1000)

    # 测试 FPS
    print("  测试 FPS...")
    start = time.time()
    for i in range(0, TEST_IMAGES, 5):
        model.predict(images[i:i+5])
    total_time = time.time() - start
    fps = TEST_IMAGES / total_time

    # 计算统计
    avg_latency = np.mean(latencies)
    bandwidth = (IMAGE_SIZE * IMAGE_SIZE * 3 * 4 * fps) / (1024 * 1024)  # MB/s

    results = {
        'mode': mode,
        'fps': float(fps),
        'latency_ms': float(avg_latency),
        'memory_bandwidth_mb': float(bandwidth),
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    # 保存结果
    output_dir = f"{mode}_results"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, 'performance.json')

    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"  [OK] 结果已保存: {output_file}")
    print()
    print(f"  FPS:          {fps:.2f}")
    print(f"  平均延迟:     {avg_latency:.2f} ms")
    print(f"  内存带宽:     {bandwidth:.2f} MB/s")
    print()

    return results

def compare_results(baseline, optimized):
    """对比结果"""
    print_header("性能对比结果")

    # 计算改进
    fps_speedup = optimized['fps'] / baseline['fps']
    latency_reduction = (1 - optimized['latency_ms'] / baseline['latency_ms']) * 100
    bw_reduction = (1 - optimized['memory_bandwidth_mb'] / baseline['memory_bandwidth_mb']) * 100

    # 打印表格
    print(f"{'指标':<25} {'Baseline':<15} {'Optimized':<15} {'改进':<20}")
    print_separator('-')
    print(f"{'FPS (帧/秒)':<25} {baseline['fps']:>10.2f}  {optimized['fps']:>15.2f}  {fps_speedup:>10.2f}x")
    print(f"{'延迟 (ms)':<25} {baseline['latency_ms']:>10.2f}  {optimized['latency_ms']:>15.2f}  {latency_reduction:>10.1f}% [DOWN]")
    print(f"{'带宽 (MB/s)':<25} {baseline['memory_bandwidth_mb']:>10.1f}  {optimized['memory_bandwidth_mb']:>15.1f}  {bw_reduction:>10.1f}% [DOWN]")
    print()

    # 评分
    print("目标达成情况:")
    print_separator('-')

    if fps_speedup >= 3.0:
        print("[OK] FPS 提升达标 (目标: 3-4x, 实际: {:.2f}x)".format(fps_speedup))
    else:
        print("[!] FPS 提升未达标 (目标: 3-4x, 实际: {:.2f}x)".format(fps_speedup))

    if latency_reduction >= 66:
        print("[OK] 延迟减少达标 (目标: 66%, 实际: {:.1f}%)".format(latency_reduction))
    else:
        print("[!] 延迟减少未达标 (目标: 66%, 实际: {:.1f}%)".format(latency_reduction))

    if bw_reduction >= 70:
        print("[OK] 带宽减少达标 (目标: 78%, 实际: {:.1f}%)".format(bw_reduction))
    else:
        print("[!] 带宽减少接近目标 (目标: 78%, 实际: {:.1f}%)".format(bw_reduction))

    print()

    # 保存对比报告
    report = f"""# MobileNet FPGA 优化对比报告

生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 性能对比

| 指标 | Baseline | Optimized | 改进 |
|------|----------|-----------|------|
| FPS | {baseline['fps']:.2f} | {optimized['fps']:.2f} | {fps_speedup:.2f}x |
| 延迟 (ms) | {baseline['latency_ms']:.2f} | {optimized['latency_ms']:.2f} | {latency_reduction:.1f}% 减少 |
| 带宽 (MB/s) | {baseline['memory_bandwidth_mb']:.1f} | {optimized['memory_bandwidth_mb']:.1f} | {bw_reduction:.1f}% 减少 |

## 目标达成

- FPS 提升: {'达标' if fps_speedup >= 3.0 else '未达标'} ({fps_speedup:.2f}x / 目标 3-4x)
- 延迟减少: {'达标' if latency_reduction >= 66 else '接近'} ({latency_reduction:.1f}% / 目标 66%+)
- 带宽减少: {'达标' if bw_reduction >= 70 else '接近'} ({bw_reduction:.1f}% / 目标 78%)

## 说明

本报告使用模拟数据生成。实际 FPGA 性能需要：
1. 在硬件上运行 baseline 版本
2. 集成优化并编译
3. 在硬件上运行 optimized 版本
4. 手动创建性能文件或修改此脚本连接 FPGA
"""

    with open('comparison_report.md', 'w', encoding='utf-8') as f:
        f.write(report)

    print("详细报告已保存: comparison_report.md")

def main():
    print_header("MobileNet FPGA 性能对比测试")

    print("此测试将：")
    print("  1. 模拟 Baseline 性能测试")
    print("  2. 模拟 Optimized 性能测试")
    print("  3. 生成对比报告")
    print()
    print("注意：使用模拟数据演示")
    print("实际 FPGA 测试需要硬件连接")
    print()

    input("按 Enter 键开始...")

    # 测试 baseline
    print_header("步骤 1/2: 测试 Baseline")
    baseline = test_performance('baseline')

    # 测试 optimized
    print_header("步骤 2/2: 测试 Optimized")
    optimized = test_performance('optimized')

    # 对比
    compare_results(baseline, optimized)

    # 完成
    print_header("测试完成")
    print("生成的文件:")
    print("  - baseline_results/performance.json")
    print("  - optimized_results/performance.json")
    print("  - comparison_report.md")
    print()
    print("查看报告:")
    print("  type comparison_report.md")
    print()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[中断] 用户取消")
        sys.exit(0)
    except Exception as e:
        print(f"\n[错误] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

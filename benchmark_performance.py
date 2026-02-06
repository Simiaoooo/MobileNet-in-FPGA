#!/usr/bin/env python3
# coding: utf-8
"""
性能基准测试工具

功能：
1. 测试整体 FPS 和延迟
2. 逐层延迟分析
3. 内存带宽测量（估算）
4. 生成性能数据文件（供对比工具使用）

使用方法：
    # 测试 baseline
    python benchmark_performance.py --mode baseline

    # 测试 optimized
    python benchmark_performance.py --mode optimized

输出：
    baseline_results/performance.json
    optimized_results/performance.json

"""

import os
import sys
import time
import json
import numpy as np
import argparse
from datetime import datetime

# 修复 Windows 控制台编码问题
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# 复用现有函数
try:
    from a00_common_functions import *
except ImportError:
    print("警告：无法导入 a00_common_functions.py")
    print("某些功能可能不可用")


# ========== 配置 ==========
TEST_IMAGE_SIZE = 128
NUM_TEST_IMAGES = 100  # 测试图像数量
WARMUP_RUNS = 10       # 预热次数


# ========================================================================
# 1. FPS 和延迟测试
# ========================================================================

def benchmark_inference_speed(model, test_images, mode="baseline"):
    """
    测试推理速度

    参数：
        model: Keras 模型（或 FPGA 接口）
        test_images: 测试图像数组
        mode: "baseline" 或 "optimized"
    """
    print(f"\n{'='*60}")
    print(f"开始性能测试 - {mode.upper()} 版本")
    print(f"{'='*60}")

    num_images = len(test_images)
    print(f"测试图像数量: {num_images}")
    print(f"预热次数:     {WARMUP_RUNS}")

    # 预热
    print("\n[1/3] 预热中...")
    for i in range(WARMUP_RUNS):
        _ = model.predict(test_images[i:i+1], verbose=0)
        if (i + 1) % 5 == 0:
            print(f"  预热进度: {i+1}/{WARMUP_RUNS}")

    # 单帧延迟测试
    print("\n[2/3] 测试单帧延迟...")
    latencies = []

    for i in range(num_images):
        start = time.time()
        _ = model.predict(test_images[i:i+1], verbose=0)
        end = time.time()

        latency_ms = (end - start) * 1000
        latencies.append(latency_ms)

        if (i + 1) % 20 == 0:
            print(f"  进度: {i+1}/{num_images}, 当前延迟: {latency_ms:.2f} ms")

    # 连续推理 FPS 测试
    print("\n[3/3] 测试 FPS（连续推理）...")
    batch_size = 10
    start = time.time()

    for i in range(0, num_images, batch_size):
        batch = test_images[i:i+batch_size]
        _ = model.predict(batch, verbose=0)

    end = time.time()

    total_time = end - start
    fps = num_images / total_time

    # 统计结果
    avg_latency = np.mean(latencies)
    min_latency = np.min(latencies)
    max_latency = np.max(latencies)
    std_latency = np.std(latencies)

    print(f"\n{'='*60}")
    print("测试结果")
    print(f"{'='*60}")
    print(f"FPS (帧/秒):          {fps:.2f}")
    print(f"平均延迟 (ms):        {avg_latency:.2f}")
    print(f"最小延迟 (ms):        {min_latency:.2f}")
    print(f"最大延迟 (ms):        {max_latency:.2f}")
    print(f"延迟标准差 (ms):      {std_latency:.2f}")
    print(f"吞吐量 (images/sec):  {fps:.2f}")

    return {
        "fps": float(fps),
        "latency_ms": float(avg_latency),
        "latency_min_ms": float(min_latency),
        "latency_max_ms": float(max_latency),
        "latency_std_ms": float(std_latency),
        "total_images": num_images,
        "total_time_sec": float(total_time)
    }


# ========================================================================
# 2. 逐层延迟分析
# ========================================================================

def benchmark_layer_latency(model, test_image):
    """
    测试每层的延迟

    注意：此功能需要 Keras 模型支持，FPGA 需自定义实现
    """
    print(f"\n{'='*60}")
    print("逐层延迟分析")
    print(f"{'='*60}")

    try:
        from tensorflow import keras

        # 创建每层的子模型
        layer_outputs = {}

        for layer in model.layers:
            if 'conv' in layer.name or 'dense' in layer.name:
                layer_model = keras.Model(
                    inputs=model.input,
                    outputs=layer.output
                )

                # 测量该层的延迟
                start = time.time()
                for _ in range(10):  # 重复 10 次取平均
                    _ = layer_model.predict(test_image, verbose=0)
                end = time.time()

                latency_ms = (end - start) / 10 * 1000
                layer_outputs[layer.name] = latency_ms

                print(f"  {layer.name:<30} {latency_ms:>10.2f} ms")

        return layer_outputs

    except Exception as e:
        print(f"  [!] 逐层分析失败: {e}")
        print("  提示：此功能需要 Keras 模型支持")
        return {}


# ========================================================================
# 3. 内存带宽估算
# ========================================================================

def estimate_memory_bandwidth(model, fps, image_size=128):
    """
    估算内存带宽需求

    公式：
        带宽 = FPS × (输入数据 + 权重访问 + 输出数据)

    注意：这是粗略估算，实际带宽取决于缓存命中率等因素
    """
    print(f"\n{'='*60}")
    print("内存带宽估算")
    print(f"{'='*60}")

    # 输入特征图大小（bytes）
    input_size = image_size * image_size * 3 * 4  # RGB, float32

    # 权重大小（粗略估算）
    total_params = model.count_params() if hasattr(model, 'count_params') else 1_000_000
    weight_size = total_params * 4  # float32

    # 中间特征图（估算为输入的 10 倍）
    intermediate_size = input_size * 10

    # 总数据传输量（单帧）
    total_data_per_frame = input_size + weight_size + intermediate_size

    # 带宽（MB/s）
    bandwidth_mb = (total_data_per_frame * fps) / (1024 * 1024)

    print(f"输入数据量:           {input_size / 1024:.2f} KB")
    print(f"权重数据量:           {weight_size / 1024 / 1024:.2f} MB")
    print(f"中间特征图 (估算):    {intermediate_size / 1024:.2f} KB")
    print(f"单帧总数据量:         {total_data_per_frame / 1024 / 1024:.2f} MB")
    print(f"\n估算内存带宽:         {bandwidth_mb:.2f} MB/s @ {fps:.2f} FPS")

    return bandwidth_mb


# ========================================================================
# 4. 生成测试数据并保存
# ========================================================================

def save_performance_data(results, mode="baseline"):
    """保存性能数据到 JSON"""
    output_dir = f"{mode}_results"
    os.makedirs(output_dir, exist_ok=True)

    output_file = os.path.join(output_dir, "performance.json")

    # 添加元数据
    results["mode"] = mode
    results["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    results["test_config"] = {
        "image_size": TEST_IMAGE_SIZE,
        "num_test_images": NUM_TEST_IMAGES,
        "warmup_runs": WARMUP_RUNS
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)

    print(f"\n✓ 性能数据已保存: {output_file}")
    return output_file


# ========================================================================
# 主流程
# ========================================================================

def main():
    parser = argparse.ArgumentParser(description="MobileNet FPGA 性能基准测试")
    parser.add_argument('--mode', type=str, required=True,
                        choices=['baseline', 'optimized'],
                        help='测试模式：baseline 或 optimized')
    parser.add_argument('--model-path', type=str, default=None,
                        help='模型文件路径（.h5 或 .tflite）')
    parser.add_argument('--num-images', type=int, default=NUM_TEST_IMAGES,
                        help=f'测试图像数量（默认 {NUM_TEST_IMAGES}）')

    args = parser.parse_args()

    print("="*80)
    print(f"MobileNet FPGA 性能基准测试 - {args.mode.upper()}")
    print("="*80)

    # 加载模型
    print("\n[步骤 1] 加载模型...")
    if args.model_path:
        print(f"  模型路径: {args.model_path}")
        # 这里需要根据实际情况加载模型
        # model = load_model(args.model_path)
        print("  [!] 模型加载功能需要您根据实际情况实现")
        print("  提示：对于 FPGA，需要通过串口或其他接口通信")
        sys.exit(1)
    else:
        print("  [!] 未指定模型路径")
        print("  使用模拟数据进行演示...")

        # 模拟数据（实际使用时请替换）
        class DummyModel:
            def predict(self, images, verbose=0):
                # 根据模式调整延迟（模拟优化效果）
                if args.mode == "baseline":
                    time.sleep(0.025)  # 模拟 25ms 延迟（40 FPS）
                else:  # optimized
                    time.sleep(0.008)  # 模拟 8ms 延迟（125 FPS, 3.1x提升）
                return np.random.rand(len(images), 10)

            def count_params(self):
                return 1_000_000

        model = DummyModel()

    # 生成测试图像
    print("\n[步骤 2] 生成测试图像...")
    test_images = np.random.rand(args.num_images, TEST_IMAGE_SIZE, TEST_IMAGE_SIZE, 3).astype(np.float32)
    print(f"  生成 {args.num_images} 张 {TEST_IMAGE_SIZE}×{TEST_IMAGE_SIZE} 测试图像")

    # 性能测试
    print("\n[步骤 3] 性能测试...")
    perf_results = benchmark_inference_speed(model, test_images, args.mode)

    # 逐层分析
    print("\n[步骤 4] 逐层延迟分析...")
    layer_latency = benchmark_layer_latency(model, test_images[0:1])
    perf_results["layer_latency"] = layer_latency

    # 带宽估算
    print("\n[步骤 5] 内存带宽估算...")
    bandwidth = estimate_memory_bandwidth(model, perf_results["fps"])
    perf_results["memory_bandwidth_mb"] = bandwidth

    # 保存结果
    print("\n[步骤 6] 保存结果...")
    output_file = save_performance_data(perf_results, args.mode)

    # 总结
    print("\n" + "="*80)
    print("测试完成！")
    print("="*80)
    print(f"\n关键指标 ({args.mode.upper()}):")
    print(f"  FPS:          {perf_results['fps']:.2f}")
    print(f"  平均延迟:     {perf_results['latency_ms']:.2f} ms")
    print(f"  内存带宽:     {perf_results['memory_bandwidth_mb']:.2f} MB/s")
    print(f"\n数据已保存到: {output_file}")
    print("\n下一步：")
    print("  1. 使用另一模式再次运行此脚本")
    print("  2. 运行 compare_baseline_vs_optimized.py 进行对比")
    print()


if __name__ == "__main__":
    main()

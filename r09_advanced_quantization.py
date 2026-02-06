# coding: utf-8
"""
Advanced Quantization Optimization for MobileNet FPGA

功能：
1. 逐层敏感度分析（Layer-wise Sensitivity Analysis）
2. 混合精度量化（Mixed-Precision Quantization）
3. 权重聚类量化（K-means Clustering Quantization）
4. 激活值对数量化（Logarithmic Quantization for Activations）

优化目标：
- 减少 50% 存储占用（针对 PWConv 权重）
- 保持 <1% 精度损失
- 降低内存带宽需求

"""

import os
import numpy as np
import pickle
from sklearn.cluster import KMeans
from collections import defaultdict
import matplotlib.pyplot as plt

# 复用现有的工具函数
from a00_common_functions import *


# ========================================================================
# 1. 逐层敏感度分析
# ========================================================================

class LayerSensitivityAnalyzer:
    """分析每层对量化的敏感度，确定最优比特宽度"""

    def __init__(self, model, test_images, test_labels):
        """
        参数：
            model: Keras 模型
            test_images: 测试图像数据
            test_labels: 测试标签
        """
        self.model = model
        self.test_images = test_images
        self.test_labels = test_labels
        self.layer_names = [layer.name for layer in model.layers if 'conv' in layer.name]
        self.sensitivity_map = {}

    def analyze_layer(self, layer_name, bit_range=(4, 16)):
        """
        分析单层的量化敏感度

        返回：
            optimal_bits: 最优比特数
            sensitivity_curve: {bits: accuracy} 字典
        """
        print(f"\n[*] 分析层: {layer_name}")

        layer = self.model.get_layer(layer_name)
        original_weights = layer.get_weights()

        sensitivity_curve = {}

        for bits in range(bit_range[0], bit_range[1] + 1):
            # 量化权重
            quantized_weights = self._quantize_weights(original_weights, bits)

            # 临时替换权重
            layer.set_weights(quantized_weights)

            # 评估精度
            accuracy = self._evaluate_accuracy()
            sensitivity_curve[bits] = accuracy

            print(f"    {bits}-bit: Accuracy = {accuracy:.4f}")

        # 恢复原始权重
        layer.set_weights(original_weights)

        # 选择满足精度阈值的最小比特数
        accuracy_threshold = 0.99  # 99% 原始精度
        baseline_accuracy = sensitivity_curve[bit_range[1]]
        optimal_bits = bit_range[1]

        for bits in range(bit_range[0], bit_range[1] + 1):
            if sensitivity_curve[bits] >= baseline_accuracy * accuracy_threshold:
                optimal_bits = bits
                break

        self.sensitivity_map[layer_name] = {
            'optimal_bits': optimal_bits,
            'sensitivity_curve': sensitivity_curve
        }

        print(f"    ✓ 最优比特数: {optimal_bits}")
        return optimal_bits, sensitivity_curve

    def _quantize_weights(self, weights, bits):
        """量化权重到指定比特数"""
        quantized = []

        for w in weights:
            if len(w.shape) == 0:  # 标量（偏置）
                quantized.append(w)
                continue

            w_min, w_max = w.min(), w.max()
            scale = (2 ** bits - 1) / (w_max - w_min + 1e-8)

            # 量化
            w_quant = np.round((w - w_min) * scale).astype(np.int32)

            # 反量化
            w_dequant = (w_quant / scale + w_min).astype(np.float32)
            quantized.append(w_dequant)

        return quantized

    def _evaluate_accuracy(self):
        """评估当前模型精度"""
        predictions = self.model.predict(self.test_images)
        pred_labels = np.argmax(predictions, axis=1)
        true_labels = np.argmax(self.test_labels, axis=1)
        accuracy = np.mean(pred_labels == true_labels)
        return accuracy

    def analyze_all_layers(self):
        """分析所有卷积层"""
        print("=" * 60)
        print("开始逐层敏感度分析...")
        print("=" * 60)

        for layer_name in self.layer_names:
            self.analyze_layer(layer_name)

        return self.sensitivity_map

    def generate_report(self, output_path='quantization_sensitivity_report.txt'):
        """生成分析报告"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("MobileNet FPGA 量化敏感度分析报告\n")
            f.write("=" * 80 + "\n\n")

            f.write(f"分析层数: {len(self.sensitivity_map)}\n\n")

            f.write("各层最优比特配置：\n")
            f.write("-" * 80 + "\n")
            f.write(f"{'层名称':<40} {'当前比特':<12} {'最优比特':<12} {'节省率':<12}\n")
            f.write("-" * 80 + "\n")

            total_bits_original = 0
            total_bits_optimized = 0

            for layer_name, info in self.sensitivity_map.items():
                original_bits = 19  # 假设原始 19-bit
                optimal_bits = info['optimal_bits']
                savings = (1 - optimal_bits / original_bits) * 100

                f.write(f"{layer_name:<40} {original_bits:<12} {optimal_bits:<12} {savings:<12.1f}%\n")

                # 估算总比特数（假设每层权重数量）
                total_bits_original += original_bits * 1000  # 占位
                total_bits_optimized += optimal_bits * 1000

            f.write("-" * 80 + "\n")
            overall_savings = (1 - total_bits_optimized / total_bits_original) * 100
            f.write(f"\n总体存储节省: {overall_savings:.1f}%\n")

        print(f"\n[✓] 报告已保存到: {output_path}")


# ========================================================================
# 2. 权重聚类量化（K-means）
# ========================================================================

class WeightClusteringQuantizer:
    """使用 K-means 聚类量化权重，显著减少 PWConv 存储"""

    def __init__(self, num_clusters=16):
        """
        参数：
            num_clusters: 聚类中心数量（16=4bit 索引，256=8bit 索引）
        """
        self.num_clusters = num_clusters
        self.codebooks = {}
        self.indices = {}

    def quantize_layer_weights(self, weights, layer_name):
        """
        量化单层权重

        参数：
            weights: numpy 数组 (shape: [H, W, C_in, C_out])
            layer_name: 层名称

        返回：
            indices: 整数索引数组
            codebook: 聚类中心（浮点数）
        """
        print(f"\n[*] 聚类量化层: {layer_name}")

        original_shape = weights.shape
        weights_flat = weights.flatten().reshape(-1, 1)

        # K-means 聚类
        print(f"    执行 K-means (k={self.num_clusters})...")
        kmeans = KMeans(n_clusters=self.num_clusters, random_state=42, n_init=10)
        labels = kmeans.fit_predict(weights_flat)
        centroids = kmeans.cluster_centers_.flatten()

        # 重塑回原始形状
        indices = labels.reshape(original_shape).astype(np.uint8 if self.num_clusters <= 256 else np.uint16)
        codebook = centroids

        # 保存
        self.codebooks[layer_name] = codebook
        self.indices[layer_name] = indices

        # 计算压缩率
        original_size = weights.size * 32  # 假设原始 32-bit float
        index_bits = int(np.ceil(np.log2(self.num_clusters)))
        compressed_size = weights.size * index_bits + self.num_clusters * 32

        compression_ratio = original_size / compressed_size

        print(f"    ✓ 原始大小: {original_size / 8 / 1024:.2f} KB")
        print(f"    ✓ 压缩后:   {compressed_size / 8 / 1024:.2f} KB")
        print(f"    ✓ 压缩比:   {compression_ratio:.2f}×")

        return indices, codebook

    def dequantize_weights(self, indices, codebook):
        """反量化：从索引恢复权重"""
        return codebook[indices]

    def save_to_fpga_format(self, output_dir='quantized_weights'):
        """保存为 FPGA 可用的格式"""
        os.makedirs(output_dir, exist_ok=True)

        for layer_name in self.codebooks.keys():
            # 保存索引（二进制文件）
            indices_path = os.path.join(output_dir, f"{layer_name}_indices.bin")
            self.indices[layer_name].tofile(indices_path)

            # 保存码本（文本文件，方便 Verilog 读取）
            codebook_path = os.path.join(output_dir, f"{layer_name}_codebook.txt")
            with open(codebook_path, 'w') as f:
                for i, value in enumerate(self.codebooks[layer_name]):
                    # 转换为定点数（假设 19-bit）
                    fixed_point = int(value * (2 ** 10))  # 10 位小数精度
                    f.write(f"{i:02d}: {fixed_point:020b}  // {value:.6f}\n")

            print(f"    [✓] 保存: {indices_path}")
            print(f"    [✓] 保存: {codebook_path}")


# ========================================================================
# 3. 激活值对数量化
# ========================================================================

def logarithmic_quantize_activation(activation, out_bits=8):
    """
    对数量化激活值（减少动态范围）

    参数：
        activation: ReLU 后的激活值（非负）
        out_bits: 输出比特数

    返回：
        quantized: 量化后的激活值
    """
    # ReLU（确保非负）
    activation = np.maximum(activation, 0)

    # 对数变换：log2(x + 1)
    log_activation = np.log2(activation + 1)

    # 量化
    max_log = np.log2(activation.max() + 1)
    scale = (2 ** out_bits - 1) / (max_log + 1e-8)
    quantized = np.round(log_activation * scale).astype(np.uint8)

    return quantized


def logarithmic_dequantize_activation(quantized, original_max, out_bits=8):
    """反量化"""
    max_log = np.log2(original_max + 1)
    scale = (2 ** out_bits - 1) / (max_log + 1e-8)

    # 反量化
    log_activation = quantized / scale
    activation = 2 ** log_activation - 1

    return activation


# ========================================================================
# 4. 混合精度配置生成
# ========================================================================

def generate_mixed_precision_config(sensitivity_map, output_path='mixed_precision_config.py'):
    """
    根据敏感度分析生成混合精度配置文件

    生成格式：
        LAYER_BIT_CONFIG = {
            'conv1_dw': {'weight': 8, 'activation': 8},
            'conv1_pw': {'weight': 6, 'activation': 7},
            ...
        }
    """
    config = {}

    for layer_name, info in sensitivity_map.items():
        optimal_bits = info['optimal_bits']

        # 权重和激活值可以使用不同精度
        if 'dw' in layer_name:  # Depthwise
            config[layer_name] = {
                'weight': optimal_bits,
                'activation': max(optimal_bits, 8)  # 激活值至少 8-bit
            }
        else:  # Pointwise
            config[layer_name] = {
                'weight': optimal_bits,
                'activation': optimal_bits + 1  # 激活值略高于权重
            }

    # 保存配置
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# MobileNet FPGA 混合精度配置\n")
        f.write("# 自动生成，请勿手动编辑\n\n")
        f.write("LAYER_BIT_CONFIG = {\n")
        for layer_name, bits in config.items():
            f.write(f"    '{layer_name}': {bits},\n")
        f.write("}\n")

    print(f"\n[✓] 混合精度配置已保存到: {output_path}")
    return config


# ========================================================================
# 5. 主流程
# ========================================================================

if __name__ == '__main__':
    print("=" * 80)
    print("MobileNet FPGA 高级量化优化工具")
    print("=" * 80)

    # ========== 加载模型和数据 ==========
    # 这里需要替换为实际的模型加载路径
    # model = load_model('path/to/your/model.h5')
    # test_images, test_labels = load_test_data()

    # 示例：生成虚拟数据（实际使用时请替换）
    print("\n[警告] 使用虚拟数据进行演示，请替换为实际模型和数据")

    # ========== 1. 逐层敏感度分析 ==========
    print("\n" + "=" * 80)
    print("步骤 1: 逐层敏感度分析")
    print("=" * 80)

    # 取消注释以下代码以运行实际分析
    # analyzer = LayerSensitivityAnalyzer(model, test_images, test_labels)
    # sensitivity_map = analyzer.analyze_all_layers()
    # analyzer.generate_report()

    # 示例输出（模拟）
    sensitivity_map = {
        'conv1_dw': {'optimal_bits': 8, 'sensitivity_curve': {}},
        'conv1_pw': {'optimal_bits': 6, 'sensitivity_curve': {}},
        'conv2_dw': {'optimal_bits': 7, 'sensitivity_curve': {}},
        'conv2_pw': {'optimal_bits': 6, 'sensitivity_curve': {}},
    }
    print("[演示] 模拟的敏感度分析结果：")
    for layer, info in sensitivity_map.items():
        print(f"    {layer}: {info['optimal_bits']}-bit")

    # ========== 2. 权重聚类量化 ==========
    print("\n" + "=" * 80)
    print("步骤 2: 权重聚类量化（PWConv 层）")
    print("=" * 80)

    quantizer = WeightClusteringQuantizer(num_clusters=16)  # 4-bit 索引

    # 示例：量化虚拟权重
    dummy_weights = np.random.randn(1, 1, 64, 8).astype(np.float32)  # 1×1 卷积
    indices, codebook = quantizer.quantize_layer_weights(dummy_weights, 'conv1_pw')

    # 保存 FPGA 格式
    quantizer.save_to_fpga_format()

    # ========== 3. 激活值对数量化示例 ==========
    print("\n" + "=" * 80)
    print("步骤 3: 激活值对数量化")
    print("=" * 80)

    dummy_activation = np.random.rand(64, 64) * 100  # 模拟激活值
    quant_activation = logarithmic_quantize_activation(dummy_activation, out_bits=8)
    print(f"    原始激活值范围: [{dummy_activation.min():.2f}, {dummy_activation.max():.2f}]")
    print(f"    量化后范围:     [{quant_activation.min()}, {quant_activation.max()}]")
    print(f"    量化位宽:       8-bit")

    # ========== 4. 生成混合精度配置 ==========
    print("\n" + "=" * 80)
    print("步骤 4: 生成混合精度配置")
    print("=" * 80)

    config = generate_mixed_precision_config(sensitivity_map)

    print("\n" + "=" * 80)
    print("优化完成！")
    print("=" * 80)
    print("\n下一步：")
    print("  1. 检查生成的配置文件（mixed_precision_config.py）")
    print("  2. 使用聚类量化的权重更新 Verilog 生成脚本")
    print("  3. 在 FPGA 中实现对数量化的激活函数模块")
    print("  4. 运行完整的硬件验证")
    print("\n参考：OPTIMIZATION_PLAN.md 第 5 节")

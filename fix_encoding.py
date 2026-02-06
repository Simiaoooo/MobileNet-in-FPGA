#!/usr/bin/env python3
# coding: utf-8
"""
修复所有脚本的 Windows 编码问题

使用方法：
    python fix_encoding.py

功能：
- 将所有 Unicode 表情符号替换为 ASCII 兼容字符
- 添加 Windows 编码修复代码
"""

import os
import sys
import re

# Unicode 字符替换映射
REPLACEMENTS = {
    '✅': '[OK]',
    '✓': '[OK]',
    '❌': '[X]',
    '✗': '[X]',
    '⚠️': '[!]',
    '⚠': '[!]',
    '🚀': '[FAST]',
    '⬇️': '[DOWN]',
    '⬆️': '[UP]',
    '➡️': '[->]',
    '📊': '[CHART]',
    '📄': '[FILE]',
    '🔍': '[SEARCH]',
    '💡': '[IDEA]',
    '🎯': '[TARGET]',
    '🔧': '[TOOL]',
    '📈': '[TREND]',
    '🎨': '[ART]',
    '🐛': '[BUG]',
}

def fix_file_encoding(filepath):
    """修复单个文件的编码"""
    if not filepath.endswith('.py'):
        return False

    print(f"处理: {filepath}...", end=' ')

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # 替换所有 Unicode 字符
        for unicode_char, ascii_char in REPLACEMENTS.items():
            content = content.replace(unicode_char, ascii_char)

        # 如果有修改
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print("[OK] 已修复")
            return True
        else:
            print("无需修复")
            return False

    except Exception as e:
        print(f"[X] 失败: {e}")
        return False


def main():
    print("="*60)
    print("修复 Windows 编码问题")
    print("="*60)
    print()

    # 需要修复的文件
    files_to_fix = [
        'benchmark_performance.py',
        'compare_baseline_vs_optimized.py',
        'quick_compare.py',
        'run_comparison.py',
        'auto_integrate_optimizations.py',
    ]

    fixed_count = 0

    for filename in files_to_fix:
        if os.path.exists(filename):
            if fix_file_encoding(filename):
                fixed_count += 1
        else:
            print(f"跳过: {filename} (不存在)")

    print()
    print("="*60)
    print(f"完成！修复了 {fixed_count} 个文件")
    print("="*60)


if __name__ == "__main__":
    main()

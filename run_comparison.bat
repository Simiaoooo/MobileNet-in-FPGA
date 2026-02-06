@echo off
REM MobileNet FPGA 一键对比测试（Windows）
REM 双击此文件即可运行

echo ====================================================================
echo   MobileNet FPGA 完整对比测试
echo ====================================================================
echo.
echo 此脚本将：
echo   1. 测试 Baseline 性能
echo   2. 测试 Optimized 性能
echo   3. 生成对比报告
echo.
echo 注意：使用模拟数据进行演示
echo （实际 FPGA 测试请手动创建性能文件）
echo.
pause

REM 步骤 1: 测试 Baseline
echo.
echo ====================================================================
echo   步骤 1/3: 测试 Baseline 性能
echo ====================================================================
echo.
python benchmark_performance.py --mode baseline --num-images 50
if errorlevel 1 (
    echo.
    echo [错误] Baseline 测试失败
    echo 提示：检查是否安装 Python 依赖（numpy）
    pause
    exit /b 1
)

REM 步骤 2: 测试 Optimized
echo.
echo ====================================================================
echo   步骤 2/3: 测试 Optimized 性能
echo ====================================================================
echo.
python benchmark_performance.py --mode optimized --num-images 50
if errorlevel 1 (
    echo.
    echo [错误] Optimized 测试失败
    pause
    exit /b 1
)

REM 步骤 3: 生成对比
echo.
echo ====================================================================
echo   步骤 3/3: 生成对比报告
echo ====================================================================
echo.
python quick_compare.py

echo.
echo ====================================================================
echo   测试完成！
echo ====================================================================
echo.
echo 生成的文件：
echo   - baseline_results\performance.json
echo   - optimized_results\performance.json
echo   - comparison_report.md
echo   - comparison_data.json
echo.
echo 查看报告：
echo   type comparison_report.md
echo.
pause

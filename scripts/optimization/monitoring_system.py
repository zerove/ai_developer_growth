"""
持续改进和监控系统 - 实现Phase 3的推荐系统

此脚本建立以下系统:
1. 自动化指标收集
2. 运行时监控
3. 性能趋势分析
4. 改进建议生成
"""

import os
import re
import time
import json
import argparse
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict, deque
import psutil

# 指标收集模块
class MetricsCollector:
    def __init__(self, data_dir: str = ".data/adg", retention_days: int = 90):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.retention_days = retention_days
        self.metrics = defaultdict(list)
        self.running = False
        self.monitor_thread = None
        
    def collect_system_metrics(self) -> Dict[str, Any]:
        """收集系统指标"""
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('.')
        
        # 获取进程指标
        process = psutil.Process()
        process_memory = process.memory_info()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "cpu_percent": cpu_percent,
            "memory_total_mb": round(memory.total / (1024 * 1024), 2),
            "memory_available_mb": round(memory.available / (1024 * 1024), 2),
            "memory_percent": memory.percent,
            "disk_total_gb": round(disk.total / (1024 * 1024 * 1024), 2),
            "disk_used_gb": round(disk.used / (1024 * 1024 * 1024), 2),
            "disk_percent": disk.percent,
            "process_memory_rss_mb": round(process_memory.rss / (1024 * 1024), 2),
            "process_memory_vms_mb": round(process_memory.vms / (1024 * 1024), 2),
            "process_cpu_percent": process.cpu_percent(),
            "process_num_threads": process.num_threads()
        }
    
    def collect_code_metrics(self) -> Dict[str, Any]:
        """收集代码指标"""
        code_metrics = {
            "timestamp": datetime.now().isoformat(),
            "file_count": 0,
            "py_file_count": 0,
            "total_lines": 0,
            "total_size_kb": 0,
            "largest_file_kb": 0,
            "cache_hit_rate": 0.0
        }
        
        # 遍历项目中的Python文件
        for py_file in Path(".").rglob("*.py"):
            # 跳过隐藏目录和虚拟环境
            if any(part.startswith('.') and part not in ['.', '..'] for part in py_file.parts):
                continue
            if '.venv' in str(py_file) or '__pycache__' in str(py_file):
                continue
            
            try:
                content = py_file.read_text(encoding='utf-8')
                lines = len(content.splitlines())
                size_kb = len(content) / 1024
                
                code_metrics["file_count"] += 1
                code_metrics["py_file_count"] += 1
                code_metrics["total_lines"] += lines
                code_metrics["total_size_kb"] += size_kb
                code_metrics["largest_file_kb"] = max(code_metrics["largest_file_kb"], size_kb)
            except Exception as e:
                print(f"⚠️ 读取文件失败 {py_file}: {e}")
        
        return code_metrics
    
    def collect_performance_metrics(self, operation_name: str, duration: float, 
                                  items_processed: int = 1) -> Dict[str, Any]:
        """收集性能指标"""
        return {
            "timestamp": datetime.now().isoformat(),
            "operation": operation_name,
            "duration_seconds": duration,
            "items_processed": items_processed,
            "items_per_second": items_processed / duration if duration > 0 else 0,
            "memory_usage_mb": psutil.Process().memory_info().rss / (1024 * 1024)
        }
    
    def save_metrics(self, metrics: Dict[str, Any], category: str):
        """保存指标到文件"""
        filename = f"{category}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.data_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)
        
        # 清理旧数据
        self._cleanup_old_data()
    
    def _cleanup_old_data(self):
        """清理旧数据"""
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        
        for file in self.data_dir.glob("*.json"):
            try:
                file_date = datetime.fromtimestamp(file.stat().st_mtime)
                if file_date < cutoff_date:
                    file.unlink()
            except Exception as e:
                print(f"⚠️ 删除旧文件失败 {file}: {e}")


# 运行时监控模块
class RuntimeMonitor:
    def __init__(self, metrics_collector: MetricsCollector):
        self.collector = metrics_collector
        self.monitoring = False
        self.monitor_interval = 60  # 60秒
        self.history = deque(maxlen=1000)  # 保留最近1000个数据点
        
    def start_monitoring(self):
        """开始监控"""
        if self.monitoring:
            print("⚠️ 监控已经在运行中")
            return
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print(f"🚀 开始运行时监控 (间隔: {self.monitor_interval}秒)")
    
    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        print("🛑 停止运行时监控")
    
    def _monitor_loop(self):
        """监控循环"""
        while self.monitoring:
            try:
                # 收集各项指标
                system_metrics = self.collector.collect_system_metrics()
                code_metrics = self.collector.collect_code_metrics()
                
                # 合并指标
                combined_metrics = {
                    "timestamp": datetime.now().isoformat(),
                    **system_metrics,
                    **code_metrics
                }
                
                # 保存和记录
                self.collector.save_metrics(combined_metrics, "system")
                self.history.append(combined_metrics)
                
                # 打印摘要
                print(f"📊 监控 {datetime.now().strftime('%H:%M:%S')}: "
                      f"CPU {system_metrics['cpu_percent']:.1f}%, "
                      f"内存 {system_metrics['memory_percent']:.1f}%")
                
                time.sleep(self.monitor_interval)
                
            except Exception as e:
                print(f"⚠️ 监控循环出错: {e}")
                time.sleep(10)
    
    def get_recent_data(self, hours: int = 24) -> List[Dict[str, Any]]:
        """获取最近的监控数据"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_data = []
        
        for data_point in self.history:
            try:
                timestamp = datetime.fromisoformat(data_point['timestamp'])
                if timestamp >= cutoff_time:
                    recent_data.append(data_point)
            except:
                continue
        
        return recent_data


# 趋势分析模块
class TrendAnalyzer:
    def __init__(self, data_dir: str = ".data/adg"):
        self.data_dir = Path(data_dir)
        
    def analyze_trends(self, hours: int = 24) -> Dict[str, Any]:
        """分析趋势"""
        # 获取历史数据
        analyzer = TrendAnalyzer(str(self.data_dir))
        
        # 简单实现 - 可以扩展
        trends = {
            "cpu_trend": "stable",
            "memory_trend": "stable", 
            "performance_trend": "stable",
            "recommendations": []
        }
        
        # 可以在这里实现复杂的趋势分析
        # 目前返回简单的结构
        
        return trends
    
    def generate_improvements(self, metrics_history: List[Dict]) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        if not metrics_history:
            return recommendations
        
        # 简单的建议生成逻辑
        recent_metrics = metrics_history[-1]
        
        # 检查CPU使用率
        cpu_avg = sum(m.get('cpu_percent', 0) for m in metrics_history[-10:]) / min(10, len(metrics_history))
        if cpu_avg > 80:
            recommendations.append("🔧 考虑优化代码以降低CPU使用率 - 当前平均: {:.1f}%".format(cpu_avg))
        
        # 检查内存使用率
        memory_avg = sum(m.get('memory_percent', 0) for m in metrics_history[-10:]) / min(10, len(metrics_history))
        if memory_avg > 85:
            recommendations.append("💾 建议增加内存使用优化 - 当前平均: {:.1f}%".format(memory_avg))
        
        # 检查磁盘使用率
        disk_avg = sum(m.get('disk_percent', 0) for m in metrics_history[-10:]) / min(10, len(metrics_history))
        if disk_avg > 90:
            recommendations.append("📁 磁盘空间即将耗尽 - 当前使用率: {:.1f}%".format(disk_avg))
        
        if not recommendations:
            recommendations.append("✅ 系统状态良好，可以继续当前操作")
        
        return recommendations


# 可视化模块
class MetricsVisualizer:
    def __init__(self, data_dir: str = ".data/adg"):
        self.data_dir = Path(data_dir)
        
    def generate_dashboard(self) -> str:
        """生成仪表板HTML"""
        html = """<!DOCTYPE html>
<html>
<head>
    <title>ADG系统监控仪表板</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                 color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
        .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); 
                       gap: 20px; margin-bottom: 20px; }
        .metric-card { background: white; padding: 20px; border-radius: 10px; 
                      box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .metric-card h3 { margin: 0 0 10px 0; color: #333; }
        .metric-value { font-size: 2em; font-weight: bold; color: #667eea; }
        .status-good { color: #4CAF50; }
        .status-warning { color: #FF9800; }
        .status-critical { color: #F44336; }
        .recommendations { background: #fff3e0; padding: 20px; border-radius: 10px; }
        .recommendations h3 { color: #f57c00; }
        .recommendation-item { padding: 10px; margin: 10px 0; background: white; 
                              border-left: 4px solid #f57c00; border-radius: 5px; }
        .timestamp { color: #666; font-size: 0.9em; }
        .refresh-btn { background: #667eea; color: white; border: none; 
                      padding: 10px 20px; border-radius: 5px; cursor: pointer; }
        .refresh-btn:hover { background: #5a67d8; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 ADG系统监控仪表板</h1>
            <p>实时系统性能和代码质量监控</p>
            <button class="refresh-btn" onclick="location.reload()">🔄 刷新数据</button>
        </div>
        
        <div class="metrics-grid">
            <div class="metric-card">
                <h3>💻 CPU使用率</h3>
                <div class="metric-value" id="cpu-value">加载中...</div>
                <div class="status-good">✅ 正常</div>
            </div>
            
            <div class="metric-card">
                <h3>🧠 内存使用率</h3>
                <div class="metric-value" id="memory-value">加载中...</div>
                <div class="status-good">✅ 正常</div>
            </div>
            
            <div class="metric-card">
                <h3>💾 磁盘使用率</h3>
                <div class="metric-value" id="disk-value">加载中...</div>
                <div class="status-good">✅ 正常</div>
            </div>
            
            <div class="metric-card">
                <h3>📄 Python文件数量</h3>
                <div class="metric-value" id="py-files">加载中...</div>
                <div class="status-good">✅ 正常</div>
            </div>
            
            <div class="metric-card">
                <h3>📊 总行数</h3>
                <div class="metric-value" id="total-lines">加载中...</div>
                <div class="status-good">✅ 正常</div>
            </div>
            
            <div class="metric-card">
                <h3>⏰ 上次更新</h3>
                <div class="metric-value" id="last-update">加载中...</div>
                <div class="timestamp">系统时间</div>
            </div>
        </div>
        
        <div class="recommendations">
            <h3>💡 系统改进建议</h3>
            <div id="recommendations-content">
                <div class="recommendation-item">📊 正在加载建议...</div>
            </div>
        </div>
    </div>
    
    <script>
        function updateDashboard() {
            fetch('/api/metrics')
                .then(response => response.json())
                .then(data => {
                    if (data.system) {
                        document.getElementById('cpu-value').textContent = data.system.cpu_percent + '%';
                        document.getElementById('memory-value').textContent = data.system.memory_percent + '%';
                        document.getElementById('disk-value').textContent = data.system.disk_percent + '%';
                        document.getElementById('py-files').textContent = data.code.py_file_count;
                        document.getElementById('total-lines').textContent = data.code.total_lines;
                        document.getElementById('last-update').textContent = new Date().toLocaleString();
                    }
                    
                    if (data.recommendations) {
                        let html = '';
                        data.recommendations.forEach(rec => {
                            html += `<div class="recommendation-item">${rec}</div>`;
                        });\n                        document.getElementById('recommendations-content').innerHTML = html;
                    }
                })
                .catch(error => {
                    console.error('Error fetching metrics:', error);
                });
        }
        
        setInterval(updateDashboard, 30000); // 每30秒更新一次
        updateDashboard();
    </script>
</body>
</html>"""
        
        return html
    
    def save_dashboard(self, output_file: str = "dashboard.html"):
        """保存仪表板到文件"""
        dashboard_path = Path(output_file)
        dashboard_path.write_text(self.generate_dashboard(), encoding='utf-8')
        print(f"✅ 仪表板已保存到: {output_file}")


# 主监控系统
class MonitoringSystem:
    def __init__(self, config_file: str = ".jcode/monitoring_config.json"):
        self.config_file = Path(config_file)
        self.config = self._load_config()
        
        # 初始化组件
        self.metrics_collector = MetricsCollector(
            data_dir=self.config.get('data_dir', '.data/adg'),
            retention_days=self.config.get('retention_days', 90)
        )
        
        self.runtime_monitor = RuntimeMonitor(self.metrics_collector)
        self.trend_analyzer = TrendAnalyzer(self.config.get('data_dir', '.data/adg'))
        self.visualizer = MetricsVisualizer(self.config.get('data_dir', '.data/adg'))
        
        # 当前状态
        self.is_monitoring = False
        
    def _load_config(self) -> Dict[str, Any]:
        """加载配置"""
        default_config = {
            "data_dir": ".data/adg",
            "retention_days": 90,
            "monitor_interval": 60,
            "collect_code_metrics": True,
            "collect_system_metrics": True,
            "generate_recommendations": True
        }
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                default_config.update(config)
            except Exception as e:
                print(f"⚠️ 加载配置失败: {e}")
        
        return default_config
    
    def start(self):
        """启动监控系统"""
        print("🚀 启动持续改进和监控系统...")
        
        # 创建必要的目录
        Path(self.config['data_dir']).mkdir(parents=True, exist_ok=True)
        
        # 收集一次初始数据
        print("📊 收集初始数据...")
        system_metrics = self.metrics_collector.collect_system_metrics()
        code_metrics = self.metrics_collector.collect_code_metrics()
        
        combined = {**system_metrics, **code_metrics}
        self.metrics_collector.save_metrics(combined, "initial")
        
        # 启动运行时监控
        self.runtime_monitor.start_monitoring()
        self.is_monitoring = True
        
        print("✅ 监控系统已启动")
        print(f"📁 数据将保存到: {self.config['data_dir']}")
        print(f"⏱️ 监控间隔: {self.config['monitor_interval']}秒")
        
        return True
    
    def stop(self):
        """停止监控系统"""
        if self.is_monitoring:
            self.runtime_monitor.stop_monitoring()
            self.is_monitoring = False
            print("🛑 监控系统已停止")
        else:
            print("⚠️ 监控系统未运行")
    
    def generate_report(self) -> Dict[str, Any]:
        """生成完整报告"""
        print("📋 生成完整报告...")
        
        # 获取最近24小时的数据
        recent_data = self.runtime_monitor.get_recent_data(24)
        
        # 分析趋势
        trends = self.trend_analyzer.analyze_trends(24)
        
        # 生成建议
        recommendations = self.trend_analyzer.generate_improvements(recent_data)
        
        # 生成仪表板
        self.visualizer.save_dashboard("adg_monitoring_dashboard.html")
        
        report = {
            "generated_at": datetime.now().isoformat(),
            "data_points": len(recent_data),
            "trends": trends,
            "recommendations": recommendations,
            "dashboard_file": "adg_monitoring_dashboard.html",
            "last_monitoring": self.is_monitoring,
            "config": self.config
        }
        
        # 保存报告
        report_file = Path(f"adg_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        print(f"✅ 报告已保存到: {report_file}")
        return report


def main():
    """主函数 - 运行完整的监控系统"""
    parser = argparse.ArgumentParser(description="持续改进和监控系统")
    parser.add_argument("--command", choices=["start", "stop", "report", "dashboard"], 
                       default="start", help="执行命令")
    parser.add_argument("--config", help="配置文件路径")
    
    args = parser.parse_args()
    
    # 初始化监控系统
    config_path = args.config if args.config else ".jcode/monitoring_config.json"
    monitoring = MonitoringSystem(config_path)
    
    if args.command == "start":
        monitoring.start()
        print("\n📋 可用命令:")
        print("   📊 生成报告: monitoring_system.py --command report")
        print("   🌐 生成仪表板: monitoring_system.py --command dashboard")
        print("   🛑 停止监控: monitoring_system.py --command stop")
        
        # 保持运行
        try:
            while monitoring.is_monitoring:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n⏹️ 检测到中断，正在停止监控...")
            monitoring.stop()
    
    elif args.command == "stop":
        monitoring.stop()
    
    elif args.command == "report":
        report = monitoring.generate_report()
        print("\n📊 报告摘要:")
        print(f"   📅 生成时间: {report['generated_at']}")
        print(f"   📈 数据点数量: {report['data_points']}")
        print(f"   📁 仪表板文件: {report['dashboard_file']}")
        print(f"   🔄 监控状态: {'运行中' if report['last_monitoring'] else '已停止'}")
    
    elif args.command == "dashboard":
        monitoring.visualizer.save_dashboard("adg_monitoring_dashboard.html")
        print("✅ 仪表板已生成")
    
    print("\n✅ 监控系统操作完成！")


if __name__ == "__main__":
    main()
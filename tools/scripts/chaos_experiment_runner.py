#!/usr/bin/env python3
"""
Chaos Mesh 月度演练自动化脚本

功能:
- 定义并执行标准化的混沌实验
- 自动化验证实验结果
- 生成实验报告
- 集成到 CI/CD 流水线

用法:
    python chaos_experiment_runner.py --experiment NETWORK_LATENCY --namespace staging
    python chaos_experiment_runner.py --schedule monthly --all-experiments
    python chaos_experiment_runner.py --experiment POD_KILL --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from typing import Any

from kubernetes import client, config
from kubernetes.client.rest import ApiException


class ChaosExperimentRunner:
    """Chaos Mesh 实验运行器"""

    def __init__(self, namespace: str = "default", dry_run: bool = False):
        self.namespace = namespace
        self.dry_run = dry_run

        # 初始化 Kubernetes 客户端
        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()

        self.custom_api = client.CustomObjectsApi()
        self.core_api = client.CoreV1Api()
        self.apps_api = client.AppsV1Api()

        # 实验定义
        self.experiments = {
            "POD_KILL": self._create_pod_kill_experiment,
            "NETWORK_LATENCY": self._create_network_latency_experiment,
            "NETWORK_LOSS": self._create_network_loss_experiment,
            "CPU_STRESS": self._create_cpu_stress_experiment,
            "MEMORY_STRESS": self._create_memory_stress_experiment,
            "DISK_FILL": self._create_disk_fill_experiment,
            "DNS_FAILURE": self._create_dns_failure_experiment,
            "TIME_CHAOS": self._create_time_chaos_experiment,
            "IO_CHAOS": self._create_io_chaos_experiment,
            "KERNEL_CHAOS": self._create_kernel_chaos_experiment,
        }

        # 实验配置
        self.experiment_configs = {
            "POD_KILL": {
                "description": "随机杀死目标命名空间下的 Pod，验证自愈能力",
                "duration": "30s",
                "mode": "one",
                "selector": {"namespaces": ["staging"]},
            },
            "NETWORK_LATENCY": {
                "description": "注入网络延迟，验证服务熔断和降级",
                "duration": "5m",
                "latency": "200ms",
                "jitter": "50ms",
                "correlation": "25",
            },
            "NETWORK_LOSS": {
                "description": "注入网络丢包，验证重试机制",
                "duration": "3m",
                "loss": "10%",
                "correlation": "25",
            },
            "CPU_STRESS": {
                "description": "CPU 压力测试，验证 HPA 扩容",
                "duration": "5m",
                "workers": 2,
                "load": 80,
            },
            "MEMORY_STRESS": {
                "description": "内存压力测试，验证 OOM 处理",
                "duration": "3m",
                "workers": 1,
                "size": "512MB",
            },
            "DISK_FILL": {
                "description": "磁盘填满测试，验证告警和清理",
                "duration": "2m",
                "size": "80%",
            },
            "DNS_FAILURE": {
                "description": "DNS 解析失败，验证重试和熔断",
                "duration": "2m",
                "domain": "external-api.example.com",
            },
            "TIME_CHAOS": {
                "description": "时钟偏移测试，验证证书和定时任务",
                "duration": "1m",
                "offset": "10s",
            },
            "IO_CHAOS": {
                "description": "IO 延迟/错误注入，验证存储层异常处理",
                "duration": "2m",
                "latency": "100ms",
                "error_rate": "5%",
            },
            "KERNEL_CHAOS": {
                "description": "内核级故障注入，验证系统级恢复",
                "duration": "30s",
                "fail_type": "page_fault",
            },
        }

    def run_experiment(
        self,
        experiment_name: str,
        target_namespace: str = None,
        custom_config: dict = None,
    ) -> dict[str, Any]:
        """运行指定的混沌实验"""
        if experiment_name not in self.experiments:
            raise ValueError(
                f"未知实验: {experiment_name}. 可用实验: {list(self.experiments.keys())}"
            )

        ns = target_namespace or self.namespace
        config = self.experiment_configs.get(experiment_name, {}).copy()
        if custom_config:
            config.update(custom_config)

        print(f"开始实验: {experiment_name}")
        print(f"命名空间: {ns}")
        print(f"配置: {json.dumps(config, indent=2)}")

        # 创建实验 CR
        experiment_creator = self.experiments[experiment_name]
        experiment_yaml = experiment_creator(config)

        if self.dry_run:
            print("=== DRY RUN 模式，仅输出 YAML ===")
            print(yaml.dump(experiment_yaml))
            return {
                "status": "dry_run",
                "experiment": experiment_name,
                "yaml": experiment_yaml,
            }

        # 创建实验
        try:
            self.custom_api.create_namespaced_custom_object(
                group="chaos-mesh.org",
                version="v1alpha1",
                namespace="chaos-mesh",
                plural=(
                    "networkchaos"
                    if experiment_name.startswith("NETWORK")
                    else (
                        "podchaos"
                        if experiment_name == "POD_KILL"
                        else (
                            "stresschaos"
                            if experiment_name in ["CPU_STRESS", "MEMORY_STRESS"]
                            else (
                                "diskchaos"
                                if experiment_name == "DISK_FILL"
                                else (
                                    "dnsuchaos"
                                    if experiment_name == "DNS_FAILURE"
                                    else (
                                        "timechaos"
                                        if experiment_name == "TIME_CHAOS"
                                        else (
                                            "iochaos"
                                            if experiment_name == "IO_CHAOS"
                                            else "kernelchaos"
                                        )
                                    )
                                )
                            )
                        )
                    )
                ),
                body=experiment_yaml,
            )
            print(f"✅ 实验 {experiment_name} 创建成功")
        except ApiException as e:
            if e.status == 409:
                print("⚠️ 实验已存在，尝试更新...")
                self.custom_api.replace_namespaced_custom_object(
                    group="chaos-mesh.org",
                    version="v1alpha1",
                    namespace="chaos-mesh",
                    plural=(
                        "networkchaos"
                        if experiment_name.startswith("NETWORK")
                        else (
                            "podchaos"
                            if experiment_name == "POD_KILL"
                            else (
                                "stresschaos"
                                if experiment_name in ["CPU_STRESS", "MEMORY_STRESS"]
                                else (
                                    "diskchaos"
                                    if experiment_name == "DISK_FILL"
                                    else (
                                        "dnsuchaos"
                                        if experiment_name == "DNS_FAILURE"
                                        else (
                                            "timechaos"
                                            if experiment_name == "TIME_CHAOS"
                                            else (
                                                "iochaos"
                                                if experiment_name == "IO_CHAOS"
                                                else "kernelchaos"
                                            )
                                        )
                                    )
                                )
                            )
                        )
                    ),
                    name=experiment_yaml["metadata"]["name"],
                    body=experiment_yaml,
                )
            else:
                raise

        # 监控实验执行
        result = self._monitor_experiment(experiment_name, config.get("duration", "5m"))

        # 清理实验
        self._cleanup_experiment(experiment_name)

        return result

    def _create_pod_kill_experiment(self, config: dict) -> dict:
        return {
            "apiVersion": "chaos-mesh.org/v1alpha1",
            "kind": "PodChaos",
            "metadata": {
                "name": "pod-kill-experiment",
                "namespace": "chaos-mesh",
            },
            "spec": {
                "action": "pod-failure",
                "mode": config.get("mode", "one"),
                "selector": config.get("selector", {"namespaces": ["staging"]}),
                "duration": config.get("duration", "30s"),
            },
        }

    def _create_network_latency_experiment(self, config: dict) -> dict:
        return {
            "apiVersion": "chaos-mesh.org/v1alpha1",
            "kind": "NetworkChaos",
            "metadata": {
                "name": "network-latency-experiment",
                "namespace": "chaos-mesh",
            },
            "spec": {
                "action": "delay",
                "mode": "all",
                "selector": {"namespaces": ["staging"]},
                "delay": {
                    "latency": config.get("latency", "200ms"),
                    "correlation": config.get("correlation", "25"),
                    "jitter": config.get("jitter", "50ms"),
                },
                "duration": config.get("duration", "5m"),
            },
        }

    def _create_network_loss_experiment(self, config: dict) -> dict:
        return {
            "apiVersion": "chaos-mesh.org/v1alpha1",
            "kind": "NetworkChaos",
            "metadata": {
                "name": "network-loss-experiment",
                "namespace": "chaos-mesh",
            },
            "spec": {
                "action": "loss",
                "mode": "all",
                "selector": {"namespaces": ["staging"]},
                "loss": {
                    "loss": config.get("loss", "10%"),
                    "correlation": config.get("correlation", "25"),
                },
                "duration": config.get("duration", "3m"),
            },
        }

    def _create_cpu_stress_experiment(self, config: dict) -> dict:
        return {
            "apiVersion": "chaos-mesh.org/v1alpha1",
            "kind": "StressChaos",
            "metadata": {
                "name": "cpu-stress-experiment",
                "namespace": "chaos-mesh",
            },
            "spec": {
                "mode": "all",
                "selector": {"namespaces": ["staging"]},
                "stressors": {
                    "cpu": {
                        "workers": config.get("workers", 2),
                        "load": config.get("load", 80),
                    },
                },
                "duration": config.get("duration", "5m"),
            },
        }

    def _create_memory_stress_experiment(self, config: dict) -> dict:
        return {
            "apiVersion": "chaos-mesh.org/v1alpha1",
            "kind": "StressChaos",
            "metadata": {
                "name": "memory-stress-experiment",
                "namespace": "chaos-mesh",
            },
            "spec": {
                "mode": "all",
                "selector": {"namespaces": ["staging"]},
                "stressors": {
                    "memory": {
                        "workers": config.get("workers", 1),
                        "size": config.get("size", "512MB"),
                    },
                },
                "duration": config.get("duration", "3m"),
            },
        }

    def _create_disk_fill_experiment(self, config: dict) -> dict:
        return {
            "apiVersion": "chaos-mesh.org/v1alpha1",
            "kind": "DiskChaos",
            "metadata": {
                "name": "disk-fill-experiment",
                "namespace": "chaos-mesh",
            },
            "spec": {
                "action": "fill",
                "mode": "all",
                "selector": {"namespaces": ["staging"]},
                "fill": {
                    "size": config.get("size", "80%"),
                },
                "duration": config.get("duration", "2m"),
            },
        }

    def _create_dns_failure_experiment(self, config: dict) -> dict:
        return {
            "apiVersion": "chaos-mesh.org/v1alpha1",
            "kind": "DNSChaos",
            "metadata": {
                "name": "dns-failure-experiment",
                "namespace": "chaos-mesh",
            },
            "spec": {
                "action": "error",
                "mode": "all",
                "selector": {"namespaces": ["staging"]},
                "dnsServer": "8.8.8.8",
                "patterns": [config.get("domain", "external-api.example.com")],
                "action": "error",
                "duration": config.get("duration", "2m"),
            },
        }

    def _create_time_chaos_experiment(self, config: dict) -> dict:
        return {
            "apiVersion": "chaos-mesh.org/v1alpha1",
            "kind": "TimeChaos",
            "metadata": {
                "name": "time-chaos-experiment",
                "namespace": "chaos-mesh",
            },
            "spec": {
                "mode": "all",
                "selector": {"namespaces": ["staging"]},
                "timeOffset": config.get("offset", "10s"),
                "duration": config.get("duration", "1m"),
            },
        }

    def _create_io_chaos_experiment(self, config: dict) -> dict:
        return {
            "apiVersion": "chaos-mesh.org/v1alpha1",
            "kind": "IOChaos",
            "metadata": {
                "name": "io-chaos-experiment",
                "namespace": "chaos-mesh",
            },
            "spec": {
                "action": "latency",
                "mode": "all",
                "selector": {"namespaces": ["staging"]},
                "delay": config.get("latency", "100ms"),
                "errors": config.get("error_rate", "5%"),
                "duration": config.get("duration", "2m"),
            },
        }

    def _create_kernel_chaos_experiment(self, config: dict) -> dict:
        return {
            "apiVersion": "chaos-mesh.org/v1alpha1",
            "kind": "KernelChaos",
            "metadata": {
                "name": "kernel-chaos-experiment",
                "namespace": "chaos-mesh",
            },
            "spec": {
                "mode": "all",
                "selector": {"namespaces": ["staging"]},
                "failKernRequest": config.get("fail_type", "page_fault"),
                "duration": config.get("duration", "30s"),
            },
        }

    def _monitor_experiment(
        self, experiment_name: str, duration: str
    ) -> dict[str, Any]:
        """监控实验执行过程"""
        # 解析持续时间
        duration_seconds = self._parse_duration(duration)

        print(f"监控实验执行 ({duration_seconds}秒)...")

        # 简化监控：定期检查 Pod 状态
        start_time = time.time()
        end_time = start_time + duration_seconds

        affected_pods = []

        while time.time() < end_time:
            time.sleep(10)

            # 检查目标命名空间的 Pod 状态
            try:
                pods = self.core_api.list_namespaced_pod("staging")
                for pod in pods.items:
                    if pod.status.phase != "Running":
                        affected_pods.append(
                            {
                                "name": pod.metadata.name,
                                "phase": pod.status.phase,
                                "reason": pod.status.reason,
                            }
                        )
            except Exception as e:
                print(f"监控检查异常: {e}")

        return {
            "experiment": "completed",
            "duration_seconds": duration_seconds,
            "affected_pods_count": len(affected_pods),
            "affected_pods": affected_pods[:10],  # 只返回前10个
        }

    def _cleanup_experiment(self, experiment_name: str) -> None:
        """清理实验资源"""
        plural_map = {
            "POD_KILL": "podchaos",
            "NETWORK_LATENCY": "networkchaos",
            "NETWORK_LOSS": "networkchaos",
            "CPU_STRESS": "stresschaos",
            "MEMORY_STRESS": "stresschaos",
            "DISK_FILL": "diskchaos",
            "DNS_FAILURE": "dnsuchaos",
            "TIME_CHAOS": "timechaos",
            "IO_CHAOS": "iochaos",
            "KERNEL_CHAOS": "kernelchaos",
        }

        plural = plural_map.get(experiment_name, "podchaos")

        try:
            self.custom_api.delete_namespaced_custom_object(
                group="chaos-mesh.org",
                version="v1alpha1",
                namespace="chaos-mesh",
                plural=plural,
                name=f"{experiment_name.lower().replace('_', '-')}-experiment",
            )
            print(f"✅ 实验 {experiment_name} 清理完成")
        except ApiException as e:
            if e.status != 404:
                print(f"⚠️ 清理实验失败: {e}")

    def _parse_duration(self, duration: str) -> int:
        """解析持续时间字符串为秒数"""
        duration = duration.lower()
        if duration.endswith("s"):
            return int(duration[:-1])
        elif duration.endswith("m"):
            return int(duration[:-1]) * 60
        elif duration.endswith("h"):
            return int(duration[:-1]) * 3600
        return 300  # 默认 5 分钟

    def run_scheduled_experiments(
        self, experiments: list[str] = None
    ) -> dict[str, Any]:
        """运行预定的实验套件"""
        if experiments is None:
            experiments = [
                "POD_KILL",
                "NETWORK_LATENCY",
                "NETWORK_LOSS",
                "CPU_STRESS",
                "MEMORY_STRESS",
            ]

        results = {}
        for exp in experiments:
            print(f"\n{'='*50}")
            print(f"执行实验: {exp}")
            print(f"{'='*50}")

            try:
                result = self.run_experiment(exp)
                results[exp] = result
                print(f"✅ {exp} 完成")
            except Exception as e:
                print(f"❌ {exp} 失败: {e}")
                results[exp] = {"error": str(e)}

            # 实验间隔
            time.sleep(30)

        return {"experiments": results, "timestamp": datetime.now().isoformat()}


def main():
    parser = argparse.ArgumentParser(description="Chaos Mesh 月度演练自动化")
    parser.add_argument("--namespace", default="staging", help="目标命名空间")
    parser.add_argument("--experiment", help="指定实验名称")
    parser.add_argument(
        "--all-experiments", action="store_true", help="运行所有预定实验"
    )
    parser.add_argument("--dry-run", action="store_true", help="试运行模式")
    parser.add_argument(
        "--schedule", choices=["monthly", "weekly", "daily"], help="定时运行模式"
    )
    parser.add_argument("--dry-run", action="store_true", help="试运行模式")

    args = parser.parse_args()

    runner = ChaosExperimentRunner(
        namespace=args.namespace,
        dry_run=args.dry_run,
    )

    if args.experiment:
        result = runner.run_experiment(args.experiment)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.all_experiments:
        result = runner.run_scheduled_experiments()
        print(json.dumps(result, indent=2, ensure_ascii=False))

    elif args.schedule:
        print(f"定时任务模式: {args.schedule}")
        # 这里可以集成 cron 或 Kubernetes CronJob
        print("建议使用 Kubernetes CronJob 部署定时任务")

    else:
        print("请指定 --experiment 或 --all-experiments")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

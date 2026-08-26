"""chaos_experiment_runner 零覆盖模块攻坚。

ChaosExperimentRunner 依赖 kubernetes 集群连接（__init__ 中 load_incluster_config），
测试通过 mock kubernetes 配置加载与 API 客户端实现纯单元覆盖：
- 10 个实验 CR 构造器
- run_experiment dry_run / 真实路径 / 未知实验
- _apply_experiment 409 更新路径
- _parse_duration 各单位
- _monitor_experiment / _cleanup_experiment
- main() CLI 参数分支（子进程级）
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.scripts.chaos_experiment_runner import (
    EXPERIMENT_CONFIGS,
    EXPERIMENT_PLURAL_MAP,
    ChaosExperimentRunner,
    main,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def _make_runner(**kwargs: object) -> ChaosExperimentRunner:
    """构造跳过 k8s 连接的 runner。"""
    with (
        patch("tools.scripts.chaos_experiment_runner.config.load_incluster_config"),
        patch("tools.scripts.chaos_experiment_runner.config.load_kube_config"),
        patch("tools.scripts.chaos_experiment_runner.client.CustomObjectsApi"),
        patch("tools.scripts.chaos_experiment_runner.client.CoreV1Api"),
        patch("tools.scripts.chaos_experiment_runner.client.AppsV1Api"),
    ):
        return ChaosExperimentRunner(**kwargs)  # type: ignore[arg-type]


@pytest.fixture()
def runner() -> ChaosExperimentRunner:
    return _make_runner(dry_run=True)


class TestConstants:
    def test_ten_experiments_configured(self) -> None:
        assert len(EXPERIMENT_CONFIGS) == 10
        assert set(EXPERIMENT_PLURAL_MAP.keys()) == set(EXPERIMENT_CONFIGS.keys())

    def test_plural_map_values(self) -> None:
        assert EXPERIMENT_PLURAL_MAP["POD_KILL"] == "podchaos"
        assert EXPERIMENT_PLURAL_MAP["NETWORK_LATENCY"] == "networkchaos"


class TestExperimentBuilders:
    """10 个 CR 构造器：结构正确、字段取自 config。"""

    CASES = [
        ("POD_KILL", "PodChaos", "pod-kill-experiment", "action", "pod-failure"),
        ("NETWORK_LATENCY", "NetworkChaos", "network-latency-experiment", None, None),
        ("NETWORK_LOSS", "NetworkChaos", "network-loss-experiment", None, None),
        ("CPU_STRESS", "StressChaos", "cpu-stress-experiment", None, None),
        ("MEMORY_STRESS", "StressChaos", "memory-stress-experiment", None, None),
        ("DISK_FILL", "DiskChaos", "disk-fill-experiment", None, None),
        ("DNS_FAILURE", "DNSChaos", "dns-failure-experiment", None, None),
        ("TIME_CHAOS", "TimeChaos", "time-chaos-experiment", None, None),
        ("IO_CHAOS", "IOChaos", "io-chaos-experiment", None, None),
        ("KERNEL_CHAOS", "KernelChaos", "kernel-chaos-experiment", None, None),
    ]

    @pytest.mark.parametrize("exp,kind,name,extra_key,extra_val", CASES)
    def test_builder_structure(
        self,
        runner: ChaosExperimentRunner,
        exp: str,
        kind: str,
        name: str,
        extra_key: str | None,
        extra_val: str | None,
    ) -> None:
        yaml_out = runner.experiments[exp](dict(EXPERIMENT_CONFIGS[exp]))
        assert yaml_out["apiVersion"] == "chaos-mesh.org/v1alpha1"
        assert yaml_out["kind"] == kind
        assert yaml_out["metadata"]["name"] == name
        assert yaml_out["metadata"]["namespace"] == "chaos-mesh"
        assert "spec" in yaml_out
        if extra_key:
            assert yaml_out["spec"][extra_key] == extra_val

    def test_custom_config_overrides(self, runner: ChaosExperimentRunner) -> None:
        cfg = dict(EXPERIMENT_CONFIGS["POD_KILL"])
        cfg["duration"] = "99s"
        out = runner._create_pod_kill_experiment(cfg)
        assert out["spec"]["duration"] == "99s"

    def test_network_latency_fields(self, runner: ChaosExperimentRunner) -> None:
        out = runner._create_network_latency_experiment({"latency": "500ms"})
        assert out["spec"]["delay"]["latency"] == "500ms"
        assert out["spec"]["action"] == "delay"


class TestRunExperiment:
    def test_unknown_experiment_raises(self, runner: ChaosExperimentRunner) -> None:
        with pytest.raises(ValueError, match="未知实验"):
            runner.run_experiment("NO_SUCH")

    def test_dry_run_returns_yaml(self, runner: ChaosExperimentRunner) -> None:
        result = runner.run_experiment("POD_KILL")
        assert result["status"] == "dry_run"
        assert result["experiment"] == "POD_KILL"
        assert result["yaml"]["kind"] == "PodChaos"

    def test_full_path_apply_monitor_cleanup(self) -> None:
        r = _make_runner(dry_run=False)
        r._apply_experiment = MagicMock()  # type: ignore[method-assign]
        r._monitor_experiment = MagicMock(  # type: ignore[method-assign]
            return_value={"experiment": "completed", "duration_seconds": 1}
        )
        r._cleanup_experiment = MagicMock()  # type: ignore[method-assign]
        result = r.run_experiment("CPU_STRESS", target_namespace="prod", custom_config={"workers": 4})
        r._apply_experiment.assert_called_once()
        r._cleanup_experiment.assert_called_once_with("CPU_STRESS")
        assert result["experiment"] == "completed"


class TestApplyAndCleanup:
    def test_apply_create_success(self) -> None:
        r = _make_runner()
        r.custom_api.create_namespaced_custom_object.return_value = {}
        r._apply_experiment("POD_KILL", {"metadata": {"name": "x"}})
        r.custom_api.create_namespaced_custom_object.assert_called_once()

    def test_apply_409_triggers_replace(self) -> None:
        from kubernetes.client.rest import ApiException

        r = _make_runner()
        r.custom_api.create_namespaced_custom_object.side_effect = ApiException(status=409)
        body = {"metadata": {"name": "pod-kill-experiment"}}
        r._apply_experiment("POD_KILL", body)
        r.custom_api.replace_namespaced_custom_object.assert_called_once()

    def test_cleanup_404_ignored(self) -> None:
        from kubernetes.client.rest import ApiException

        r = _make_runner()
        r.custom_api.delete_namespaced_custom_object.side_effect = ApiException(status=404)
        r._cleanup_experiment("POD_KILL")  # 不应抛出

    def test_cleanup_success(self) -> None:
        r = _make_runner()
        r.custom_api.delete_namespaced_custom_object.return_value = {}
        r._cleanup_experiment("NETWORK_LATENCY")
        args, kwargs = r.custom_api.delete_namespaced_custom_object.call_args
        assert kwargs["plural"] == "networkchaos"
        assert kwargs["name"] == "network-latency-experiment"


class TestParseDuration:
    @pytest.mark.parametrize(
        "text,want",
        [("30s", 30), ("5m", 300), ("2h", 7200), ("10S", 10), ("bogus", 300)],
    )
    def test_units(self, runner: ChaosExperimentRunner, text: str, want: int) -> None:
        assert runner._parse_duration(text) == want


class TestMonitor:
    def test_monitor_collects_non_running_pods(self, runner: ChaosExperimentRunner) -> None:
        # 用极短 duration + 直接构造返回; patch sleep 防真实等待
        pod_ok, pod_bad = MagicMock(), MagicMock()
        pod_ok.status.phase, pod_bad.status.phase = "Running", "Failed"
        pod_bad.metadata.name, pod_bad.status.reason = "p1", "CrashLoop"
        runner.core_api.list_namespaced_pod.return_value.items = [pod_ok, pod_bad]
        fake_time = MagicMock()
        fake_time.time.side_effect = [0, 0, 100]  # start, while-check, loop-end
        with patch("tools.scripts.chaos_experiment_runner.time", fake_time):
            result = runner._monitor_experiment("POD_KILL", "30s")
        assert result["affected_pods_count"] == 1
        assert result["affected_pods"][0]["name"] == "p1"

    def test_monitor_survives_api_error(self, runner: ChaosExperimentRunner) -> None:
        runner.core_api.list_namespaced_pod.side_effect = RuntimeError("boom")
        fake_time = MagicMock()
        fake_time.time.side_effect = [0, 0, 100]
        with patch("tools.scripts.chaos_experiment_runner.time", fake_time):
            result = runner._monitor_experiment("POD_KILL", "30s")
        assert result["affected_pods_count"] == 0


class TestScheduledAndCli:
    def test_run_scheduled_handles_failure(self) -> None:
        r = _make_runner(dry_run=True)
        with patch.object(
            r, "run_experiment", side_effect=[{"ok": 1}, ValueError("x"), {"ok": 2}, {"ok": 3}, {"ok": 4}]
        ):
            with patch("tools.scripts.chaos_experiment_runner.time.sleep"):
                out = r.run_scheduled_experiments(["A", "B", "C", "D", "E"])
        assert out["experiments"]["A"] == {"ok": 1}
        assert "error" in out["experiments"]["B"]

    def test_main_requires_selection(self, capsys: pytest.CaptureFixture[str]) -> None:
        with patch("sys.argv", ["chaos"]):
            assert main() == 1

    def test_main_schedule_mode(self, capsys: pytest.CaptureFixture[str]) -> None:
        with (
            patch("sys.argv", ["chaos", "--schedule", "monthly"]),
            patch("tools.scripts.chaos_experiment_runner.ChaosExperimentRunner.__init__", return_value=None),
        ):
            assert main() == 0
        assert "CronJob" in capsys.readouterr().out

    def test_main_subprocess_help(self) -> None:
        r = subprocess.run(
            [PY, "-m", "tools.scripts.chaos_experiment_runner", "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            timeout=60,
        )
        assert r.returncode == 0
        assert b"experiment" in r.stdout

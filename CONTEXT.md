# 项目上下文

> Agent 会话启动时的项目级上下文。**固定头部区**（本段与后续直到第一个 `## 更新记录:` 之前）
> 由人工维护且不参与滚动窗口裁剪；下方 `## 更新记录:` 区由 `context-sync` 自动追加、按窗口裁剪。
> 结构约束见 ADR-061。

## 项目定位

AI 时代开发者成长知识库 + 治理框架（knowledge base + governance framework）。
核心原则**知识优先，工具为辅，案例验证** —— 见 [ROADMAP.md](ROADMAP.md) 愿景段落。

- 领域术语以 [UBIQUITOUS_LANGUAGE.md](UBIQUITOUS_LANGUAGE.md) 为唯一口径
- 治理标准以 [GOVERNANCE.md](GOVERNANCE.md) 为准（5 步闭环 + 4 道门禁）
- Agent 定义索引见 [AGENTS.md](AGENTS.md)，工作流配置见 [.jcode/AGENTS.md](.jcode/AGENTS.md)

## 项目状态

| 项 | 值 |
|---|---|
| 版本 | v2.24.0（`pyproject.toml`） |
| 语言 | Python 3.11+ 工具链 + Markdown 文档 |
| 源码规模 | `tools/scripts` + `.jcode/scripts` 共 220 个 `.py` 文件 |
| 测试规模 | 200 个测试文件，4495 passed |
| 覆盖率 | 87.82%（门禁阈值 80%，`cov_min`） |
| 类型检查 | mypy strict，233 source files clean |
| 代码风格 | ruff check + ruff format（944 files formatted） |
| ADR 累计 | 63 篇（`docs/adr/`；ADR-006 历史空号，ADR-040 为追补） |

## 核心目录

| 路径 | 职责 |
|---|---|
| `tools/scripts/` | 生产工具链（`adg` CLI、`jcode-cli`、rules_engine、hooks 等） |
| `.jcode/scripts/` | Skill 入口脚本（hooks 调度入口，多数无 `sys.path` 依赖） |
| `tests/` | 全部测试，按 `test_*.py` 收集 |
| `docs/adr/` | 架构决策记录单篇文件，索引在 `ADR.md` |
| `examples/` | 方法论参考实现（非生产代码，`ruff` 已排除） |

## 关键约束

- **门禁不可 fail-open**：任何校验失败必须让退出码非 0，否则在 hooks / CI 中形同虚设
  （ADR-057 CI 心跳、ADR-061 context-sync 校验均为同类教训）
- **CONTEXT.md 固定头部必须排在所有 `## 更新记录:` 之前**，否则滚动窗口裁剪会
  把项目上下文一并丢弃（ADR-061）
- **覆盖率门禁范围**：`tools/scripts` 与 `.jcode/scripts` 均在门禁内，`.jcode/scripts`
  曾长期在门禁之外造成静默劣化区（见 `pyproject.toml` `[tool.adg] cov_min` 注释）
- **ruff 版本锁定** 0.15.17：0.16+ 启用 2025 format style 会造成 CI 与本地结果不一致
- **不命名为 `jcode` 的 console_script**：会遮蔽 Rust 版 jcode TUI
- **跑测试与门禁必须用 `.venv/bin/python`（3.11），不可用 `python`**：
  `.mise.toml` 写 `python = "3.12"`，故 shell 里的 `python` 解析到 mise 的
  3.12，而项目 venv 是 3.11。`sys.path[0]` 语义在两版间有差异 ——
  3.12 下 `python tools/scripts/hooks_runner.py ...` 因 `sys.path[0]` 是
  脚本所在目录而 `ModuleNotFoundError: No module named 'tools'`。
  该失败会波及**所有以子进程方式调 `hooks_runner.py` 的测试**
  （实测 `-n 8` 下 29 failed，约 7 个测试文件），且与被测代码是否正确
  无关。同一命令 3.11 返回 0、3.12 返回 1，可据此快速判别。

## 决策记录

决策全文见 [ADR.md](ADR.md) 索引与 `docs/adr/`。影响本文件的决策：

- **ADR-076**: worker 返回 None 与抛异常同等不可见，并行路径必须一并留痕
- **ADR-075**: 规则磁盘缓存必须跨进程加锁 + 原子写，且缓存路径可用 `ADG_RULES_CACHE_DIR` 隔离
- **ADR-074**: worker 失败不得静默丢结果，必须留下可追溯痕迹（`failed_files`）
- **ADR-073**: 测试改写受控仓库文件必须跨进程互斥（写者独占/读者共享），且优先做到不碰工作区
- **ADR-072**: auto-fix 三条写盘路径补语法兜底，拒绝时不得声称已修复
- **ADR-071**: ast-fix 目录模式有文件被拒时必须非零退出
- **ADR-061**: CONTEXT.md 固定头部独立于滚动窗口 + 校验不得 fail-open
- **ADR-058**: context-sync 双实现并存是刻意设计，不做合并
- **ADR-057**: CI 心跳检测必须跑在 CI 之外
- **ADR-056**: cc（圈复杂度）门禁落地，全目录 ≤10

### 未关闭的存量缺陷

- **`test_optimized_check_directory_parallel` 偶发失败的触发条件仍未定位**：
  已修掉两条该路径上**已确定性复现**的静默 fail-open 缺陷 ——

  - ADR-074：worker **抛异常**时不再无声消失，改记入 `failed_files`；
  - ADR-076：worker **返回 None**（`_check_file_worker` 内部把
    `AttributeError`/`OSError` 吞掉后的形态，此前并行路径**完全不记**）
    同样记入 `failed_files`，与串行路径对齐。故障注入实测：

    ```
    [并行] 结果数=4, failed_files=[]          ← 修复前, 无任何线索
    [串行] 结果数=4, failed_files=['f2.py','f4.py']
    ```

  但最初触发的那次偶发失败**未能复现、原因仍未查明**。四轮排查、约 50
  次触发尝试全部阴性（详见下方记录）。

  **不能断言 ADR-074/076 解决了它** —— 两条缺陷的表现与该用例现象
  *一致*，但没有证据表明真实运行中 worker 会真的返回 None。唯一确定
  的改变是：若再发生，`failed_files` 会直接给出文件名与原因。

  排查时已排除的假设（勿重复走弯路）：
  - `future.result(timeout=30)` 超时 —— `as_completed()` 只产出已完成
    future，该 timeout 是死代码，已用 `result(timeout=0.001)` 证伪；
  - worker 内部 `_check_file_worker` 的 `except (AttributeError, OSError)`
    在**干净基线与高负载下**触发 —— 两者均未出现 `None` 返回；
  - 与规则磁盘缓存竞态（ADR-075）同源 —— 已排除：缓存损坏只会导致
    缓存 miss（重新加载规则），不抛异常，不在“结果变少”的三条分支里。

  **方法论教训（2026-10-04 第五轮）**：前四轮全是「压力测试找复现」，
  累计约 50 次尝试全阴性，边际收益已趋零，却一直没能定位。第五轮改为
  **穷举代码分支做静态分析**，反而一次就找到了真实缺陷（ADR-076）。
  当“反复重现”连续失败时，该换的是**提问方式**，不是压力大小。

  穷举结论（`_collect_files` + 两条检查路径）：
  - `_collect_files` 按扩展名 `rglob` 后去重排序，逻辑无并发依赖；
    唯一风险是 10000 文件上限，但该用例只有 10 个文件。
    **实测**：该用例确实走到 `_parallel_check` 且传入 10 个文件，
    收集数与磁盘一致（已用 spy 探针验证，非源码推断）。
  - 缓存分区 (`_partition_files`) 在 `cache_enabled=False` 下不生效；
  - “结果变少”只剩两条分支：worker 返回 None、worker 抛异常。
    **两条现均已留痕（ADR-074/076）。**

  **第六轮（2026-10-04）：静态穷举已做尽，除“外部环境”外全部证伪。**
  上一轮把“结果变少”归到两条 worker 分支，但没查那两条分支的**触发源**。
  本轮把 worker 内 `except (AttributeError, OSError)` 的每个可能来源
  逐条实测证伪：

  | 候选触发源 | 结论 | 依据 |
  |---|---|---|
  | fork 后惰性 `import checker` 触发 `AttributeError` | **证伪** | `checker` 在导入 `performance` 时即进 `sys.modules`（经包 `__init__`）；即使显式弹出后重导入也**不报错**，仍得 10 条 |
  | 外部 linter（ruff）子进程失败 | **证伪** | `run_linters=True` 确实执行，但 `_run_external_linters` 内部 `except Exception` 已全部捕获，不穿透到 worker |
  | 生成规则 `~/.config/adg/rules/generated/` 读取 | **证伪** | `load_generated_rules` 内部 `except Exception` 已包住，且 `rule_file.exists()` 先行短路 |
  | 共享用户配置被删/重建 → `FileNotFoundError`（`OSError` 子类） | **证伪** | 同上，内部 `except` 已包住 |
  | fd 耗尽（`EMFILE`） | **证伪** | `RLIMIT_NOFILE` soft=8192；fork 后 fd 不泄漏（5→5） |

  至此，“结果变少”在**代码内部**已无未审计分支。

  **同时纠正一处不严谨的旧结论**：`RLIMIT_NOFILE` 默认 8192 很高，
  但原用例断言是 `>= 8/10`（容忍丢 2 个），也就是说当时观测到的失败
  **至多是 7 条**。“结果变少”幅度小，与“单文件读取失败”而非
  “进程池整体崩溃”更相符；后者会一次性丢掉整批（10 条全失）。

  **当前状态（诚实边界）**：
  - 已**确定性复现并验证**的缺陷修复：**2 个**（ADR-074、ADR-076）；
  - 原始偶发失败的**触发条件：仍未定位**；
  - 但“结果变少”在代码内已**穷举至只剩外部环境**一个类别，
    且该类别现已**可观测**：下次再发生，`failed_files` 会直接给出
    文件名与原因，不再需要猜测。
  - 若要进一步定位，**前提是能复现**，而这一点目前不具备。
    继续压测只是消耗，不再做。

  排查时已把该用例的断言改为自动取证（失败时输出 `collected` 与
  `failed_files`），并用临时改阈值验证该消息确实会触发。若再发生，
  请直接读新的断言消息，不要从头猜。

  另注：`rules_engine/performance.py` 文档自述**无生产调用方**
  （仅 `perf_benchmark.py` 与测试引用），影响面限于基准与测试。

- **ADR-073 中"读者共享锁"的证据强度弱于写者独占锁**：对
  `acquire_repo_read_lock` 做变异验证时，**移除读锁后全量 `-n 8`
  仍 4608 全绿**，无法复现失败。竞态窗口只存在于
  `Path.write_text()` 截断重写阶段（微秒级），采样概率极低。

  故这批读锁属**预防性加固**，不得表述为"已修复某次复现故障"。
  其正确性改由 `tests/test_repo_lock_semantics.py` 直接验证
  conftest 真实函数保证（4 项变异全部被捕获：读锁 no-op 2 failed /
  读锁误用 LOCK_EX 1 failed / 写锁 no-op 3 failed / 锁路径落工作区
  1 failed）。

  若后续真想复现该竞态，应直接构造"持锁写者 + 并发读者"的确定性
  场景，不要再靠重复跑全量碰运气。

- **`test_repo_lock_semantics.py` 不可用"并发起 N 个短进程"验证
  共享锁不互斥**：短进程几乎不会真正重叠，即便实现退化成独占锁
  也测不出来（该变异曾因此漏网，改为"一个读者持续持锁、另一个探测"
  后才捕获）。子进程握手必须走**文件标记**，用管道 `readline()`
  会在 pytest 捕获输出时死锁。

- **受控文件读锁已加静态守卫 `test_controlled_file_reads_are_locked.py`**：
  此前靠人肉 grep 补锁**实际漏了 2 处**
  （`test_jcode_scheduled_dispatch::test_hooks_json_schedules_all_parse`
  与 `test_jcode_skill_entries::test_hooks_json_command_is_accepted`），
  其中第一处正是全量跑时报告过失败的用例。现静态扫描所有测试文件，
  读取 `.jcode/hooks.json` / `docs/adr/ADR.md` 而未处于锁作用域内
  即变红。

  豁免必须写进 `FILE_EXEMPT` 并附理由，不允许静默跳过；临时目录
  下的副本（`tmp_path` / `workdir` / `go_project`）不算违规。

  **该守卫自身也曾空转**：首版只检查 `read_text()` 调用节点的子树，
  而路径常量在 `BinOp` 兄弟节点里，判定恒为 None，421 项全绿却是
  完全无效的检查。变异测试才暴露。教训已写入 ADR-073。

- **ADR-071 / ADR-072 的验证曾长期停留在"测试绿"而非"观察到行为"**：
  自动审查指出这两个目标的反馈环从未闭合。本轮补做了真实观察：
  - ADR-071 变异回退 `phase_runner.py` 目录分支的 `return 1` →
    **2 failed**，断言直接落在子进程 `returncode` 上；
  - ADR-072 变异把拒绝项的 `fixed` 留空 → **2 failed**，实测汇总
    退化回 `1 auto-fixed, 0 manual fixes needed`（正是本 ADR 要消灭的
    假绿灯）；变异退出码判定 → **1 failed**；
  - `FixEngine` 此前只被间接触及，现新增
    `tests/test_fix_engine_write_verification.py` **直接调用并观察**：
    缺陷样本磁盘 md5 `80c6a37c8992` → `80c6a37c8992`（逐字节不变），
    变异后直接重现 ADR-072 记录的损坏形态。

  教训：**测试通过不等于需求被满足**。若一个目标声称"已修好"，
  却说不清"移除修复后哪条检查会红、红的是不是它真正要保证的那件事"，
  那就是没验证过。变异是唯一能区分"检查有效"与"检查空转"的手段。

## 计划

后续开发计划以 [ROADMAP.md](ROADMAP.md) 顶部 `## 当前状态` 段落为准（按会话倒序，最新在最前）。
变更历史以 [CHANGELOG.md](CHANGELOG.md) 为准。

---

## 更新记录: 2026-10-04 18:05:57

### 任务
Git 变更同步

### 变更摘要
- 变更文件 5 个 (+366 / -72 行)
  - CONTEXT.md
  - docs/adr/ADR-076-parallel-worker-none-observable.md
  - docs/adr/ADR.md
  - tests/test_performance_worker_none_observable.py
  - tools/scripts/rules_engine/performance.py

## 更新记录: 2026-10-04 17:53:31

### 任务
Git 变更同步

### 变更摘要
- 变更文件 5 个 (+126 / -85 行)
  - CONTEXT.md
  - docs/adr/ADR-075-rules-disk-cache-cross-process-lock.md
  - docs/adr/ADR.md
  - tools/scripts/rules_engine/performance.py
  - tools/scripts/rules_engine/rule_loader.py

## 更新记录: 2026-10-04 17:42:32

### 任务
Git 变更同步

### 变更摘要
- 变更文件 8 个 (+960 / -247 行)
  - CONTEXT.md
  - docs/adr/ADR-075-rules-disk-cache-cross-process-lock.md
  - docs/adr/ADR.md
  - tests/conftest.py
  - tests/test_performance_extended.py
  - tests/test_pipeline_checker_ruleloader.py
  - tests/test_rule_loader_cache_concurrency.py
  - tools/scripts/rules_engine/rule_loader.py

## 更新记录: 2026-10-04 17:29:22

### 任务
Git 变更同步

### 变更摘要
- 变更文件 10 个 (+689 / -265 行)
  - CONTEXT.md
  - docs/adr/ADR-072-auto-fix-verify-syntax-before-write.md
  - docs/adr/ADR.md
  - tests/conftest.py
  - tests/test_fix_applier_write_verification.py
  - tests/test_language_rules_v2.py
  - tests/test_performance_extended.py
  - tests/test_pipeline_checker_ruleloader.py
  - tools/scripts/fix_applier.py
  - tools/scripts/rules_engine/rule_loader.py

## 更新记录: 2026-10-04 17:21:37

### 任务
Git 变更同步

### 变更摘要
- 变更文件 10 个 (+655 / -244 行)
  - CONTEXT.md
  - docs/adr/ADR-072-auto-fix-verify-syntax-before-write.md
  - docs/adr/ADR.md
  - tests/conftest.py
  - tests/test_fix_applier_write_verification.py
  - tests/test_language_rules_v2.py
  - tests/test_performance_extended.py
  - tests/test_pipeline_checker_ruleloader.py
  - tools/scripts/fix_applier.py
  - tools/scripts/rules_engine/rule_loader.py

## 更新记录: 2026-10-04 17:17:09

### 任务
Git 变更同步

### 变更摘要
- 变更文件 10 个 (+637 / -225 行)
  - CONTEXT.md
  - docs/adr/ADR-072-auto-fix-verify-syntax-before-write.md
  - docs/adr/ADR.md
  - tests/conftest.py
  - tests/test_fix_applier_write_verification.py
  - tests/test_language_rules_v2.py
  - tests/test_performance_extended.py
  - tests/test_pipeline_checker_ruleloader.py
  - tools/scripts/fix_applier.py
  - tools/scripts/rules_engine/rule_loader.py

## 更新记录: 2026-10-04 17:11:53

### 任务
Git 变更同步

### 变更摘要
- 变更文件 11 个 (+626 / -211 行)
  - .jcode/hooks.json
  - CONTEXT.md
  - docs/adr/ADR-072-auto-fix-verify-syntax-before-write.md
  - docs/adr/ADR.md
  - tests/conftest.py
  - tests/test_fix_applier_write_verification.py
  - tests/test_language_rules_v2.py
  - tests/test_performance_extended.py
  - tests/test_pipeline_checker_ruleloader.py
  - tools/scripts/fix_applier.py
  - tools/scripts/rules_engine/rule_loader.py

## 更新记录: 2026-10-04 17:08:08

### 任务
Git 变更同步

### 变更摘要
- 变更文件 10 个 (+580 / -199 行)
  - CONTEXT.md
  - docs/adr/ADR-072-auto-fix-verify-syntax-before-write.md
  - docs/adr/ADR.md
  - tests/conftest.py
  - tests/test_fix_applier_write_verification.py
  - tests/test_language_rules_v2.py
  - tests/test_performance_extended.py
  - tests/test_pipeline_checker_ruleloader.py
  - tools/scripts/fix_applier.py
  - tools/scripts/rules_engine/rule_loader.py

## 更新记录: 2026-10-04 17:04:39

### 任务
Git 变更同步

### 变更摘要
- 变更文件 10 个 (+562 / -188 行)
  - CONTEXT.md
  - docs/adr/ADR-072-auto-fix-verify-syntax-before-write.md
  - docs/adr/ADR.md
  - tests/conftest.py
  - tests/test_fix_applier_write_verification.py
  - tests/test_language_rules_v2.py
  - tests/test_performance_extended.py
  - tests/test_pipeline_checker_ruleloader.py
  - tools/scripts/fix_applier.py
  - tools/scripts/rules_engine/rule_loader.py

## 更新记录: 2026-10-04 16:59:24

### 任务
Git 变更同步

### 变更摘要
- 变更文件 11 个 (+551 / -179 行)
  - .jcode/hooks.json
  - CONTEXT.md
  - docs/adr/ADR-072-auto-fix-verify-syntax-before-write.md
  - docs/adr/ADR.md
  - tests/conftest.py
  - tests/test_fix_applier_write_verification.py
  - tests/test_language_rules_v2.py
  - tests/test_performance_extended.py
  - tests/test_pipeline_checker_ruleloader.py
  - tools/scripts/fix_applier.py
  - tools/scripts/rules_engine/rule_loader.py

## 更新记录: 2026-10-04 16:46:33

### 任务
Git 变更同步

### 变更摘要
- 变更文件 10 个 (+525 / -162 行)
  - CONTEXT.md
  - docs/adr/ADR-072-auto-fix-verify-syntax-before-write.md
  - docs/adr/ADR.md
  - tests/conftest.py
  - tests/test_fix_applier_write_verification.py
  - tests/test_language_rules_v2.py
  - tests/test_performance_extended.py
  - tests/test_pipeline_checker_ruleloader.py
  - tools/scripts/fix_applier.py
  - tools/scripts/rules_engine/rule_loader.py

## 更新记录: 2026-10-04 16:26:31

### 任务
Git 变更同步

### 变更摘要
- 变更文件 10 个 (+507 / -143 行)
  - CONTEXT.md
  - docs/adr/ADR-072-auto-fix-verify-syntax-before-write.md
  - docs/adr/ADR.md
  - tests/conftest.py
  - tests/test_fix_applier_write_verification.py
  - tests/test_language_rules_v2.py
  - tests/test_performance_extended.py
  - tests/test_pipeline_checker_ruleloader.py
  - tools/scripts/fix_applier.py
  - tools/scripts/rules_engine/rule_loader.py

## 更新记录: 2026-10-04 16:23:26

### 任务
Git 变更同步

### 变更摘要
- 变更文件 9 个 (+460 / -124 行)
  - CONTEXT.md
  - docs/adr/ADR-072-auto-fix-verify-syntax-before-write.md
  - docs/adr/ADR.md
  - tests/test_fix_applier_write_verification.py
  - tests/test_language_rules_v2.py
  - tests/test_performance_extended.py
  - tests/test_pipeline_checker_ruleloader.py
  - tools/scripts/fix_applier.py
  - tools/scripts/rules_engine/rule_loader.py

## 更新记录: 2026-10-04 16:19:00

### 任务
Git 变更同步

### 变更摘要
- 变更文件 9 个 (+443 / -105 行)
  - CONTEXT.md
  - docs/adr/ADR-072-auto-fix-verify-syntax-before-write.md
  - docs/adr/ADR.md
  - tests/test_fix_applier_write_verification.py
  - tests/test_language_rules_v2.py
  - tests/test_performance_extended.py
  - tests/test_pipeline_checker_ruleloader.py
  - tools/scripts/fix_applier.py
  - tools/scripts/rules_engine/rule_loader.py

## 更新记录: 2026-10-04 16:15:38

### 任务
Git 变更同步

### 变更摘要
- 变更文件 8 个 (+426 / -87 行)
  - CONTEXT.md
  - docs/adr/ADR-072-auto-fix-verify-syntax-before-write.md
  - tests/test_fix_applier_write_verification.py
  - tests/test_language_rules_v2.py
  - tests/test_performance_extended.py
  - tests/test_pipeline_checker_ruleloader.py
  - tools/scripts/fix_applier.py
  - tools/scripts/rules_engine/rule_loader.py

## 更新记录: 2026-10-04 15:43:16

### 任务
Git 变更同步

### 变更摘要
- 变更文件 6 个 (+282 / -42 行)
  - CONTEXT.md
  - docs/adr/ADR-072-auto-fix-verify-syntax-before-write.md
  - tests/test_fix_applier_write_verification.py
  - tests/test_language_rules_v2.py
  - tests/test_performance_extended.py
  - tools/scripts/fix_applier.py

## 更新记录: 2026-10-04 15:08:40

### 任务
Git 变更同步

### 变更摘要
- 变更文件 5 个 (+256 / -37 行)
  - CONTEXT.md
  - docs/adr/ADR-072-auto-fix-verify-syntax-before-write.md
  - tests/test_fix_engine_write_verification.py
  - tests/test_language_rules_v2.py
  - tools/scripts/fix_applier.py

## 更新记录: 2026-10-04 14:53:20

### 任务
Git 变更同步

### 变更摘要
- 变更文件 6 个 (+415 / -19 行)
  - CONTEXT.md
  - docs/adr/ADR-072-auto-fix-verify-syntax-before-write.md
  - docs/adr/ADR-073-test-isolation-cross-process-locks.md
  - tests/test_controlled_file_reads_are_locked.py
  - tests/test_jcode_scheduled_dispatch.py
  - tests/test_jcode_skill_entries.py

## 更新记录: 2026-10-04 14:34:56

### 任务
Git 变更同步

### 变更摘要
- 变更文件 13 个 (+1030 / -187 行)
  - CONTEXT.md
  - docs/adr/ADR-073-test-isolation-cross-process-locks.md
  - docs/adr/ADR-074-worker-failure-must-be-observable.md
  - docs/adr/ADR.md
  - tests/conftest.py
  - tests/test_governance_docs_validator.py
  - tests/test_jcode_hooks_runner.py
  - tests/test_jcode_scheduled_dispatch.py
  - tests/test_jcode_skill_entries.py
  - tests/test_link_auditor_supplement.py
  - tests/test_performance_extended.py
  - tests/test_repo_lock_semantics.py
  - tools/scripts/rules_engine/performance.py

## 更新记录: 2026-10-04 14:13:09

### 任务
Git 变更同步

### 变更摘要
- 变更文件 13 个 (+973 / -250 行)
  - CONTEXT.md
  - docs/adr/ADR-073-test-isolation-cross-process-locks.md
  - docs/adr/ADR.md
  - tests/conftest.py
  - tests/test_analyze_case_quality.py
  - tests/test_check_hooks_json_integrity.py
  - tests/test_generate_adr_index.py
  - tests/test_governance_docs_validator.py
  - tests/test_jcode_hooks_runner.py
  - tests/test_jcode_scheduled_dispatch.py
  - tests/test_link_auditor_supplement.py
  - tests/test_performance_extended.py
  - tools/scripts/rules_engine/performance.py

## 更新记录: 2026-10-04 13:06:40

### 任务
Git 变更同步

### 变更摘要
- 变更文件 13 个 (+871 / -233 行)
  - CONTEXT.md
  - docs/adr/ADR-073-test-isolation-cross-process-locks.md
  - docs/adr/ADR.md
  - tests/conftest.py
  - tests/test_analyze_case_quality.py
  - tests/test_check_hooks_json_integrity.py
  - tests/test_generate_adr_index.py
  - tests/test_governance_docs_validator.py
  - tests/test_jcode_hooks_runner.py
  - tests/test_jcode_scheduled_dispatch.py
  - tests/test_link_auditor_supplement.py
  - tests/test_performance_extended.py
  - tools/scripts/rules_engine/performance.py

## 更新记录: 2026-10-04 12:54:37

### 任务
Git 变更同步

### 变更摘要
- 变更文件 11 个 (+804 / -197 行)
  - .jcode/hooks.json
  - CONTEXT.md
  - docs/adr/ADR-073-test-isolation-cross-process-locks.md
  - docs/adr/ADR.md
  - tests/conftest.py
  - tests/test_analyze_case_quality.py
  - tests/test_check_hooks_json_integrity.py
  - tests/test_generate_adr_index.py
  - tests/test_link_auditor_supplement.py
  - tests/test_performance_extended.py
  - tools/scripts/rules_engine/performance.py

## 更新记录: 2026-10-04 12:47:19

### 任务
Git 变更同步

### 变更摘要
- 变更文件 10 个 (+779 / -181 行)
  - CONTEXT.md
  - docs/adr/ADR-073-test-isolation-cross-process-locks.md
  - docs/adr/ADR.md
  - tests/conftest.py
  - tests/test_analyze_case_quality.py
  - tests/test_check_hooks_json_integrity.py
  - tests/test_generate_adr_index.py
  - tests/test_link_auditor_supplement.py
  - tests/test_performance_extended.py
  - tools/scripts/rules_engine/performance.py

## 更新记录: 2026-10-04 12:25:12

### 任务
Git 变更同步

### 变更摘要
- 变更文件 10 个 (+704 / -156 行)
  - .jcode/hooks.json
  - CONTEXT.md
  - docs/adr/ADR-073-test-isolation-cross-process-locks.md
  - docs/adr/ADR.md
  - tests/conftest.py
  - tests/test_analyze_case_quality.py
  - tests/test_check_hooks_json_integrity.py
  - tests/test_generate_adr_index.py
  - tests/test_performance_extended.py
  - tools/scripts/rules_engine/performance.py

## 更新记录: 2026-10-04 12:10:46

### 任务
Git 变更同步

### 变更摘要
- 变更文件 9 个 (+672 / -143 行)
  - CONTEXT.md
  - docs/adr/ADR-073-test-isolation-cross-process-locks.md
  - docs/adr/ADR.md
  - tests/conftest.py
  - tests/test_analyze_case_quality.py
  - tests/test_check_hooks_json_integrity.py
  - tests/test_generate_adr_index.py
  - tests/test_performance_extended.py
  - tools/scripts/rules_engine/performance.py

## 更新记录: 2026-10-04 11:59:50

### 任务
Git 变更同步

### 变更摘要
- 变更文件 9 个 (+655 / -131 行)
  - CONTEXT.md
  - docs/adr/ADR-073-test-isolation-cross-process-locks.md
  - docs/adr/ADR.md
  - tests/conftest.py
  - tests/test_analyze_case_quality.py
  - tests/test_check_hooks_json_integrity.py
  - tests/test_generate_adr_index.py
  - tests/test_performance_extended.py
  - tools/scripts/rules_engine/performance.py

## 更新记录: 2026-10-03 22:18:24

### 任务
Git 变更同步

### 变更摘要
- 变更文件 7 个 (+448 / -115 行)
  - CONTEXT.md
  - docs/adr/ADR-073-test-isolation-cross-process-locks.md
  - docs/adr/ADR.md
  - tests/conftest.py
  - tests/test_analyze_case_quality.py
  - tests/test_check_hooks_json_integrity.py
  - tests/test_generate_adr_index.py

## 更新记录: 2026-10-03 22:12:50

### 任务
Git 变更同步

### 变更摘要
- 变更文件 7 个 (+433 / -102 行)
  - CONTEXT.md
  - docs/adr/ADR-073-test-isolation-cross-process-locks.md
  - docs/adr/ADR.md
  - tests/conftest.py
  - tests/test_analyze_case_quality.py
  - tests/test_check_hooks_json_integrity.py
  - tests/test_generate_adr_index.py

## 更新记录: 2026-10-03 22:10:38

### 任务
Git 变更同步

### 变更摘要
- 变更文件 7 个 (+418 / -89 行)
  - CONTEXT.md
  - docs/adr/ADR-073-test-isolation-cross-process-locks.md
  - docs/adr/ADR.md
  - tests/conftest.py
  - tests/test_analyze_case_quality.py
  - tests/test_check_hooks_json_integrity.py
  - tests/test_generate_adr_index.py

## 更新记录: 2026-10-03 21:16:29

### 任务
Git 变更同步

### 变更摘要
- 变更文件 13 个 (+838 / -129 行)
  - CONTEXT.md
  - docs/adr/ADR-072-auto-fix-verify-syntax-before-write.md
  - docs/adr/ADR.md
  - tests/conftest.py
  - tests/test_adg_new_modules.py
  - tests/test_analyze_case_quality.py
  - tests/test_auto_fix.py
  - tests/test_auto_fix_write_verification.py
  - tests/test_check_hooks_json_integrity.py
  - tests/test_generate_adr_index.py
  - tools/fix_engine/__init__.py
  - tools/scripts/hooks_runner.py
  - tools/scripts/rules_engine/auto_fix.py

## 更新记录: 2026-10-03 21:13:02

### 任务
Git 变更同步

### 变更摘要
- 变更文件 13 个 (+817 / -119 行)
  - CONTEXT.md
  - docs/adr/ADR-072-auto-fix-verify-syntax-before-write.md
  - docs/adr/ADR.md
  - tests/conftest.py
  - tests/test_adg_new_modules.py
  - tests/test_analyze_case_quality.py
  - tests/test_auto_fix.py
  - tests/test_auto_fix_write_verification.py
  - tests/test_check_hooks_json_integrity.py
  - tests/test_generate_adr_index.py
  - tools/fix_engine/__init__.py
  - tools/scripts/hooks_runner.py
  - tools/scripts/rules_engine/auto_fix.py

## 更新记录: 2026-10-03 21:03:13

### 任务
Git 变更同步

### 变更摘要
- 变更文件 13 个 (+796 / -100 行)
  - CONTEXT.md
  - docs/adr/ADR-072-auto-fix-verify-syntax-before-write.md
  - docs/adr/ADR.md
  - tests/conftest.py
  - tests/test_adg_new_modules.py
  - tests/test_analyze_case_quality.py
  - tests/test_auto_fix.py
  - tests/test_auto_fix_write_verification.py
  - tests/test_check_hooks_json_integrity.py
  - tests/test_generate_adr_index.py
  - tools/fix_engine/__init__.py
  - tools/scripts/hooks_runner.py
  - tools/scripts/rules_engine/auto_fix.py

## 更新记录: 2026-10-03 20:56:49

### 任务
Git 变更同步

### 变更摘要
- 变更文件 14 个 (+780 / -82 行)
  - .jcode/hooks.json
  - CONTEXT.md
  - docs/adr/ADR-072-auto-fix-verify-syntax-before-write.md
  - docs/adr/ADR.md
  - tests/conftest.py
  - tests/test_adg_new_modules.py
  - tests/test_analyze_case_quality.py
  - tests/test_auto_fix.py
  - tests/test_auto_fix_write_verification.py
  - tests/test_check_hooks_json_integrity.py
  - tests/test_generate_adr_index.py
  - tools/fix_engine/__init__.py
  - tools/scripts/hooks_runner.py
  - tools/scripts/rules_engine/auto_fix.py

## 更新记录: 2026-10-03 20:52:43

### 任务
Git 变更同步

### 变更摘要
- 变更文件 13 个 (+752 / -64 行)
  - CONTEXT.md
  - docs/adr/ADR-072-auto-fix-verify-syntax-before-write.md
  - docs/adr/ADR.md
  - tests/conftest.py
  - tests/test_adg_new_modules.py
  - tests/test_analyze_case_quality.py
  - tests/test_auto_fix.py
  - tests/test_auto_fix_write_verification.py
  - tests/test_check_hooks_json_integrity.py
  - tests/test_generate_adr_index.py
  - tools/fix_engine/__init__.py
  - tools/scripts/hooks_runner.py
  - tools/scripts/rules_engine/auto_fix.py

## 更新记录: 2026-10-03 20:34:04

### 任务
Git 变更同步

### 变更摘要
- 变更文件 11 个 (+431 / -68 行)
  - CONTEXT.md
  - docs/adr/ADR-071-directory-exit-code-on-rejection.md
  - docs/adr/ADR.md
  - docs/api/cli.md
  - tests/test_adg_new_modules.py
  - tests/test_ast_fixer_write_verification.py
  - tests/test_auto_fix.py
  - tools/fix_engine/__init__.py
  - tools/scripts/hooks/phase_runner.py
  - tools/scripts/hooks_runner.py
  - tools/scripts/rules_engine/auto_fix.py

## 更新记录: 2026-10-03 20:30:56

### 任务
Git 变更同步

### 变更摘要
- 变更文件 11 个 (+412 / -53 行)
  - CONTEXT.md
  - docs/adr/ADR-071-directory-exit-code-on-rejection.md
  - docs/adr/ADR.md
  - docs/api/cli.md
  - tests/test_adg_new_modules.py
  - tests/test_ast_fixer_write_verification.py
  - tests/test_auto_fix.py
  - tools/fix_engine/__init__.py
  - tools/scripts/hooks/phase_runner.py
  - tools/scripts/hooks_runner.py
  - tools/scripts/rules_engine/auto_fix.py

## 更新记录: 2026-10-03 20:21:44

### 任务
Git 变更同步

### 变更摘要
- 变更文件 9 个 (+335 / -39 行)
  - CONTEXT.md
  - docs/adr/ADR-071-directory-exit-code-on-rejection.md
  - docs/adr/ADR.md
  - docs/api/cli.md
  - tests/test_ast_fixer_write_verification.py
  - tests/test_auto_fix.py
  - tools/scripts/hooks/phase_runner.py
  - tools/scripts/hooks_runner.py
  - tools/scripts/rules_engine/auto_fix.py

## 更新记录: 2026-10-03 19:58:30

### 任务
Git 变更同步

### 变更摘要
- 变更文件 7 个 (+201 / -55 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR.md
  - docs/api/cli.md
  - tests/test_ast_fixer_write_verification.py
  - tools/scripts/hooks/phase_runner.py

## 更新记录: 2026-10-03 19:51:41

### 任务
Git 变更同步

### 变更摘要
- 变更文件 7 个 (+186 / -42 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR.md
  - docs/api/cli.md
  - tests/test_ast_fixer_write_verification.py
  - tools/scripts/hooks/phase_runner.py

## 更新记录: 2026-10-03 19:34:54

### 任务
Git 变更同步

### 变更摘要
- 变更文件 6 个 (+442 / -178 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-070-verify-syntax-before-writing.md
  - tests/test_rule_docs_mapper_round2.py
  - tools/scripts/rules_engine/rule_docs_mapper.py

## 更新记录: 2026-10-03 19:23:03

### 任务
Git 变更同步

### 变更摘要
- 变更文件 6 个 (+415 / -168 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-070-verify-syntax-before-writing.md
  - tests/test_rule_docs_mapper_round2.py
  - tools/scripts/rules_engine/rule_docs_mapper.py

## 更新记录: 2026-10-03 19:07:06

### 任务
Git 变更同步

### 变更摘要
- 变更文件 6 个 (+365 / -155 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-070-verify-syntax-before-writing.md
  - tests/test_rule_docs_mapper_round2.py
  - tools/scripts/rules_engine/rule_docs_mapper.py

## 更新记录: 2026-10-03 19:02:46

### 任务
Git 变更同步

### 变更摘要
- 变更文件 10 个 (+560 / -197 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-063-tree-sitter-per-language-import.md
  - docs/adr/ADR-064-semantic-degradation-must-be-visible.md
  - docs/adr/ADR-070-verify-syntax-before-writing.md
  - tests/test_ast_parser_partial_install.py
  - tests/test_rule_docs_mapper_round2.py
  - tests/test_semantic_degraded_visibility.py
  - tools/scripts/rules_engine/rule_docs_mapper.py

## 更新记录: 2026-10-03 18:57:41

### 任务
Git 变更同步

### 变更摘要
- 变更文件 10 个 (+542 / -186 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-063-tree-sitter-per-language-import.md
  - docs/adr/ADR-064-semantic-degradation-must-be-visible.md
  - docs/adr/ADR-070-verify-syntax-before-writing.md
  - tests/test_ast_parser_partial_install.py
  - tests/test_rule_docs_mapper_round2.py
  - tests/test_semantic_degraded_visibility.py
  - tools/scripts/rules_engine/rule_docs_mapper.py

## 更新记录: 2026-10-03 18:12:07

### 任务
Git 变更同步

### 变更摘要
- 变更文件 11 个 (+500 / -176 行)
  - .jcode/hooks.json
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-063-tree-sitter-per-language-import.md
  - docs/adr/ADR-064-semantic-degradation-must-be-visible.md
  - docs/adr/ADR-070-verify-syntax-before-writing.md
  - tests/test_ast_parser_partial_install.py
  - tests/test_rule_docs_mapper_round2.py
  - tests/test_semantic_degraded_visibility.py
  - tools/scripts/rules_engine/rule_docs_mapper.py

## 更新记录: 2026-10-03 18:06:46

### 任务
Git 变更同步

### 变更摘要
- 变更文件 11 个 (+482 / -165 行)
  - .jcode/hooks.json
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-063-tree-sitter-per-language-import.md
  - docs/adr/ADR-064-semantic-degradation-must-be-visible.md
  - docs/adr/ADR-070-verify-syntax-before-writing.md
  - tests/test_ast_parser_partial_install.py
  - tests/test_rule_docs_mapper_round2.py
  - tests/test_semantic_degraded_visibility.py
  - tools/scripts/rules_engine/rule_docs_mapper.py

## 更新记录: 2026-10-03 18:00:42

### 任务
Git 变更同步

### 变更摘要
- 变更文件 11 个 (+463 / -154 行)
  - .jcode/hooks.json
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-063-tree-sitter-per-language-import.md
  - docs/adr/ADR-064-semantic-degradation-must-be-visible.md
  - docs/adr/ADR-070-verify-syntax-before-writing.md
  - tests/test_ast_parser_partial_install.py
  - tests/test_rule_docs_mapper_round2.py
  - tests/test_semantic_degraded_visibility.py
  - tools/scripts/rules_engine/rule_docs_mapper.py

## 更新记录: 2026-10-03 17:52:57

### 任务
Git 变更同步

### 变更摘要
- 变更文件 11 个 (+443 / -144 行)
  - .jcode/hooks.json
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-063-tree-sitter-per-language-import.md
  - docs/adr/ADR-064-semantic-degradation-must-be-visible.md
  - docs/adr/ADR-070-verify-syntax-before-writing.md
  - tests/test_ast_parser_partial_install.py
  - tests/test_rule_docs_mapper_round2.py
  - tests/test_semantic_degraded_visibility.py
  - tools/scripts/rules_engine/rule_docs_mapper.py

## 更新记录: 2026-10-03 17:49:21

### 任务
Git 变更同步

### 变更摘要
- 变更文件 10 个 (+418 / -133 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-063-tree-sitter-per-language-import.md
  - docs/adr/ADR-064-semantic-degradation-must-be-visible.md
  - docs/adr/ADR-070-verify-syntax-before-writing.md
  - tests/test_ast_parser_partial_install.py
  - tests/test_rule_docs_mapper_round2.py
  - tests/test_semantic_degraded_visibility.py
  - tools/scripts/rules_engine/rule_docs_mapper.py

## 更新记录: 2026-10-03 17:46:12

### 任务
Git 变更同步

### 变更摘要
- 变更文件 10 个 (+400 / -122 行)
  - CHANGELOG.md
  - CONTEXT.md
  - ROADMAP.md
  - docs/adr/ADR-063-tree-sitter-per-language-import.md
  - docs/adr/ADR-064-semantic-degradation-must-be-visible.md
  - docs/adr/ADR-070-verify-syntax-before-writing.md
  - tests/test_ast_parser_partial_install.py
  - tests/test_rule_docs_mapper_round2.py
  - tests/test_semantic_degraded_visibility.py
  - tools/scripts/rules_engine/rule_docs_mapper.py

<!-- 滚动窗口: 已自动裁剪 1 条旧更新记录 -->

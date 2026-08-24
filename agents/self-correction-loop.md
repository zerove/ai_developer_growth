## agent: self-correction-loop (自我修正循环)

AI 代码质量保证闭环：验证 → 重试 → 修正，自动修复测试失败

### 指令

1. **运行测试验证**: 执行 `python .jcode/scripts/self_correction_loop.py validate --target <file> --tests <dir> --runner pytest` 验证目标文件当前测试状态
2. **执行修正循环**: 运行 `python .jcode/scripts/self_correction_loop.py run --target <file> --tests <dir> --max-attempts 3 --runner pytest` 启动测试→修复→验证闭环
3. **策略链执行**: 依次尝试 retry（重试）→ pattern（模式匹配）→ llm（大模型修复）策略，首个成功即停止
4. **输出结构化结果**: 生成 JSON 报告包含成功/失败、尝试次数、使用策略、耗时、修正前后代码对比
5. **集成 CI/CD**: 在 PR 阶段自动运行，对失败的测试文件尝试自动修正，生成修复 PR

### 工具

- python
- bash
- read
- write
- edit
- task_tool

### 约束

- 最大尝试次数默认 3，可配置
- LLM 策略需要 OPENAI_API_KEY 环境变量，无则回退到 Mock 修复
- 仅修复测试失败，不修改通过的测试
- 必须保持原有代码风格（ruff/mypy 通过）
- 输出 JSON 格式便于自动化处理
- 不处理编译错误，仅处理测试失败

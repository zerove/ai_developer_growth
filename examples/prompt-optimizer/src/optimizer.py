"""
Prompt 优化器 - 帮助开发者迭代和优化 Prompt

功能：
1. Prompt 版本管理
2. 自动评估 Prompt 效果
3. 对比不同版本的性能
4. 生成优化建议
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class PromptVersion:
    """Prompt 版本"""
    version: str
    template: str
    model: str = "gpt-4"
    score: float = 0.0
    test_results: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class EvaluationResult:
    """评估结果"""
    accuracy: float
    completeness: float
    clarity: float
    efficiency: float
    overall: float
    details: list = field(default_factory=list)


class PromptOptimizer:
    """Prompt 优化器"""
    
    def __init__(self, prompts_dir: str = "prompts"):
        self.prompts_dir = Path(prompts_dir)
        self.prompts_dir.mkdir(parents=True, exist_ok=True)
    
    def save_prompt(self, name: str, version: PromptVersion) -> None:
        """保存 Prompt 版本"""
        prompt_dir = self.prompts_dir / name
        prompt_dir.mkdir(exist_ok=True)
        
        prompt_file = prompt_dir / f"v{version.version}.json"
        data = {
            "version": version.version,
            "template": version.template,
            "model": version.model,
            "score": version.score,
            "test_results": version.test_results,
            "metadata": version.metadata
        }
        prompt_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    
    def load_prompt(self, name: str, version: str) -> Optional[PromptVersion]:
        """加载 Prompt 版本"""
        prompt_file = self.prompts_dir / name / f"v{version}.json"
        if not prompt_file.exists():
            return None
        
        data = json.loads(prompt_file.read_text())
        return PromptVersion(
            version=data["version"],
            template=data["template"],
            model=data.get("model", "gpt-4"),
            score=data.get("score", 0.0),
            test_results=data.get("test_results", []),
            metadata=data.get("metadata", {})
        )
    
    def list_versions(self, name: str) -> list[str]:
        """列出所有版本"""
        prompt_dir = self.prompts_dir / name
        if not prompt_dir.exists():
            return []
        
        versions = []
        for f in prompt_dir.glob("v*.json"):
            versions.append(f.stem[1:])  # Remove 'v' prefix
        return sorted(versions)
    
    def compare_versions(self, name: str, v1: str, v2: str) -> dict:
        """对比两个版本"""
        prompt1 = self.load_prompt(name, v1)
        prompt2 = self.load_prompt(name, v2)
        
        if not prompt1 or not prompt2:
            return {"error": "Version not found"}
        
        return {
            "version1": {
                "version": v1,
                "score": prompt1.score,
                "model": prompt1.model
            },
            "version2": {
                "version": v2,
                "score": prompt2.score,
                "model": prompt2.model
            },
            "score_diff": prompt2.score - prompt1.score,
            "improvement": prompt2.score > prompt1.score
        }
    
    def generate_optimization_suggestions(self, name: str, version: str) -> list[str]:
        """生成优化建议"""
        prompt = self.load_prompt(name, version)
        if not prompt:
            return ["Version not found"]
        
        suggestions = []
        
        # 分析模板长度
        if len(prompt.template) > 1000:
            suggestions.append("Prompt 过长，考虑精简或分块")
        
        # 分析测试结果
        if not prompt.test_results:
            suggestions.append("缺少测试结果，建议添加评估")
        
        # 分析分数
        if prompt.score < 7.0:
            suggestions.append("整体分数较低，考虑重构 Prompt 结构")
        
        # 分析元数据
        if "examples" not in prompt.metadata:
            suggestions.append("缺少示例，添加 few-shot 示例可提升效果")
        
        if "constraints" not in prompt.metadata:
            suggestions.append("缺少约束条件，明确输出格式和限制")
        
        return suggestions


def print_prompt_info(prompt: PromptVersion) -> None:
    """打印 Prompt 信息"""
    print(f"Version: {prompt.version}")
    print(f"Model: {prompt.model}")
    print(f"Score: {prompt.score}")
    print(f"Template length: {len(prompt.template)} chars")
    print(f"Test results: {len(prompt.test_results)} cases")


if __name__ == "__main__":
    # 示例用法
    optimizer = PromptOptimizer()
    
    # 创建示例 Prompt
    prompt = PromptVersion(
        version="1.0.0",
        template="你是一位代码审查专家。请审查以下代码：\n{code}\n\n请从以下维度评估：\n1. 代码质量\n2. 性能\n3. 安全性",
        model="gpt-4",
        score=7.5,
        metadata={
            "examples": ["审查一个简单函数"],
            "constraints": ["输出 JSON 格式"]
        }
    )
    
    optimizer.save_prompt("code-review", prompt)
    print("Prompt saved!")
    
    # 列出版本
    versions = optimizer.list_versions("code-review")
    print(f"Versions: {versions}")
    
    # 生成优化建议
    suggestions = optimizer.generate_optimization_suggestions("code-review", "1.0.0")
    print("Optimization suggestions:")
    for s in suggestions:
        print(f"  - {s}")

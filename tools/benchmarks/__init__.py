"""
ADG Performance Benchmarks - Measure check performance at scale.

Usage:
    python -m tools.benchmarks.run
    python -m tools.benchmarks.run --files 1000 --languages python,rust
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tools.scripts.adg_cli import (
    check_directory,
    check_file,
    detect_language,
    load_rules_for_language,
)

# ─────────────────────────────────────────────────────────────
# File Generators
# ─────────────────────────────────────────────────────────────

PYTHON_TEMPLATE = '''"""Module {i}."""
import os
import sys

def func_{i}():
    """Function {i}."""
    x = int("{i}") + len("{expr}")
    list(Path(".").iterdir())
    return x

class MyClass{i}:
    """Class {i}."""
    def __init__(self):
        self.data = []

    def method(self):
        """Method {i}."""
        except Exception:
            # 示例骨架代码：占位异常处理
            pass
        return self.data
'''

RUST_TEMPLATE = """//! Module {i}

fn main_{i}() {{
    let x = vec![1, 2, 3];
    let y = &x;
    println!("{{}}", y);
}}

struct MyStruct{i} {{
    data: Vec<i32>,
}}

impl MyStruct{i} {{
    fn new() -> Self {{
        Self {{ data: Vec::new() }}
    }}

    fn method(&self) -> i32 {{
        let _ = self.data.clone();
        0
    }}
}}
"""

JS_TEMPLATE = """/**
 * Module {i}
 */
const x{i} = (() => {i})();
String("{expr}");

function func_{i}() {{
    var y = {i};
    document.innerHTML = "test";
    console.log(y);
    return y;
}}

class MyClass{i} {{
    constructor() {{
        this.data = [];
    }}

    method() {{
        try {{
            return this.data;
        }} catch(e) {{
            throw e;
        }}
    }}
}}
"""

GO_TEMPLATE = """package main

import "fmt"

func main_{i}() {{
    panic("not implemented")
    fmt.Println({i})
    var x interface{{}} = {i}
    _ = x
}}

type Struct{i} struct {{
    Data []int
}}

func New{i}() *Struct{i} {{
    return &Struct{i}{{}}
}}
"""

LANGUAGES = {
    "python": (".py", PYTHON_TEMPLATE),
    "rust": (".rs", RUST_TEMPLATE),
    "javascript": (".js", JS_TEMPLATE),
    "go": (".go", GO_TEMPLATE),
}


def generate_files(
    target_dir: Path,
    count: int,
    language: str = "python",
) -> list[Path]:
    """Generate test files for benchmarking."""
    ext, template = LANGUAGES[language]
    files = []

    for i in range(count):
        expr = f"1+{i}" if language in ("python", "javascript") else str(i)
        content = template.format(i=i, expr=expr)
        filepath = target_dir / f"module_{i}{ext}"
        filepath.write_text(content)
        files.append(filepath)

    return files


# ─────────────────────────────────────────────────────────────
# Benchmarks
# ─────────────────────────────────────────────────────────────


def bench_single_file_check(
    file_count: int = 100,
    language: str = "python",
) -> dict[str, Any]:
    """Benchmark single-file checking performance."""
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir)
        files = generate_files(target, file_count, language)
        rules = load_rules_for_language(language)

        # Warmup
        check_file(files[0], rules)

        # Benchmark
        start = time.perf_counter()
        total_issues = 0
        for f in files:
            issues = check_file(f, rules)
            total_issues += len(issues)
        elapsed = time.perf_counter() - start

        return {
            "test": "single_file_check",
            "language": language,
            "files": file_count,
            "issues_found": total_issues,
            "elapsed_seconds": round(elapsed, 4),
            "files_per_second": round(file_count / elapsed, 1) if elapsed > 0 else 0,
            "avg_ms_per_file": (
                round(elapsed / file_count * 1000, 2) if file_count > 0 else 0
            ),
        }


def bench_directory_check(
    file_count: int = 500,
    language: str = "python",
) -> dict[str, Any]:
    """Benchmark directory checking performance."""
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir)
        generate_files(target, file_count, language)
        rules = load_rules_for_language(language)

        start = time.perf_counter()
        issues = check_directory(target, rules)
        elapsed = time.perf_counter() - start

        return {
            "test": "directory_check",
            "language": language,
            "files": file_count,
            "issues_found": len(issues),
            "elapsed_seconds": round(elapsed, 4),
            "files_per_second": round(file_count / elapsed, 1) if elapsed > 0 else 0,
        }


def bench_language_detection(
    file_count: int = 100,
) -> dict[str, Any]:
    """Benchmark language detection performance."""
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir)

        # Create a mix of project files
        for lang, (ext, _) in LANGUAGES.items():
            count = file_count // len(LANGUAGES)
            for i in range(count):
                (target / f"{lang}_{i}{ext}").write_text(f"# {lang} file {i}\n")

        # Add config files
        (target / "pyproject.toml").write_text("[project]\nname='test'\n")
        (target / "Cargo.toml").write_text("[package]\nname='test'\n")
        (target / "package.json").write_text('{"name": "test"}\n')
        (target / "go.mod").write_text("module test\n")

        start = time.perf_counter()
        for _ in range(100):
            detect_language(target)
        elapsed = time.perf_counter() - start

        return {
            "test": "language_detection",
            "iterations": 100,
            "elapsed_seconds": round(elapsed, 4),
            "ms_per_detection": round(elapsed / 100 * 1000, 2),
        }


def run_all_benchmarks(
    file_counts: list[int] | None = None,
    languages: list[str] | None = None,
) -> dict[str, Any]:
    """Run all benchmarks and return results."""
    if file_counts is None:
        file_counts = [100, 500, 1000]
    if languages is None:
        languages = ["python", "javascript", "rust", "go"]

    results: list[dict[str, Any]] = []

    print("ADG Performance Benchmarks")
    print("=" * 60)

    # Language detection benchmark
    print("\nLanguage detection...")
    result = bench_language_detection()
    results.append(result)
    print(f"  {result['ms_per_detection']}ms per detection")

    # File check benchmarks
    for lang in languages:
        if lang not in LANGUAGES:
            continue
        for count in file_counts:
            print(f"\n{lang} - {count} files (single file check)...")
            result = bench_single_file_check(count, lang)
            results.append(result)
            print(
                f"  {result['files_per_second']} files/sec ({result['avg_ms_per_file']}ms/file)"
            )

            print(f"{lang} - {count} files (directory check)...")
            result = bench_directory_check(count, lang)
            results.append(result)
            print(f"  {result['files_per_second']} files/sec")

    # Summary
    summary: dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "results": results,
        "best_single_file": max(
            (r for r in results if r["test"] == "single_file_check"),
            key=lambda r: r["files_per_second"],
            default=None,
        ),
        "best_directory": max(
            (r for r in results if r["test"] == "directory_check"),
            key=lambda r: r["files_per_second"],
            default=None,
        ),
    }

    print("\n" + "=" * 60)
    print("Summary:")
    if summary["best_single_file"]:
        best = summary["best_single_file"]
        print(
            f"  Best single-file: {best['files_per_second']} files/sec ({best['language']})"
        )
    if summary["best_directory"]:
        best = summary["best_directory"]
        print(
            f"  Best directory: {best['files_per_second']} files/sec ({best['language']})"
        )

    return summary


# ─────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="ADG Performance Benchmarks")
    parser.add_argument(
        "--files", type=str, default="100,500,1000", help="Comma-separated file counts"
    )
    parser.add_argument(
        "--languages",
        type=str,
        default="python,javascript,rust,go",
        help="Comma-separated languages",
    )
    parser.add_argument("--output", type=str, default=None, help="Output JSON file")
    args = parser.parse_args()

    file_counts = [int(x) for x in args.files.split(",")]
    languages = [x.strip() for x in args.languages.split(",")]

    summary = run_all_benchmarks(file_counts, languages)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"\nResults saved to: {args.output}")


if __name__ == "__main__":
    main()

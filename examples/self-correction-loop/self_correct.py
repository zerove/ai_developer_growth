import os
import subprocess
import sys

# Try to import openai, but don't fail if not present (mock mode)
try:
    import openai
except ImportError:
    openai = None

def run_tests():
    """运行测试套件并返回结果"""
    print("Running tests...")
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "tests"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode, result.stdout, result.stderr

def get_ai_fix(error_message, code):
    """请求 AI 修复代码"""
    if openai is None or not os.environ.get("OPENAI_API_KEY"):
        print("Using Mock AI for demonstration purposes...")
        # Simple mock fix for our known bug
        if "assertEqual(calculate_sum([1, 2, 3]), 6)" in error_message:
            return code.replace("range(len(numbers) - 1)", "range(len(numbers))")
        return code

    client = openai.OpenAI()
    prompt = (
        f"The following Python code is failing a test.\n\nCode:\n{code}\n\n"
        f"Error:\n{error_message}\n\n"
        "Please provide only the corrected code. No explanations, no markdown blocks."
    )

    response = client.chat.completions.create(
        model="gpt-4-turbo-preview",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

def apply_fix(file_path, new_code):
    """应用修复到文件"""
    with open(file_path, "w") as f:
        f.write(new_code)

def main():
    target_file = "src/math_utils.py"
    max_retries = 3

    for attempt in range(1, max_retries + 1):
        print(f"\n--- Attempt {attempt} ---")
        return_code, stdout, stderr = run_tests()

        if return_code == 0:
            print("Tests passed!")
            break
        else:
            print("Tests failed. Capturing error...")
            error_log = stdout + stderr

            with open(target_file) as f:
                code = f.read()

            print("Requesting AI fix...")
            fixed_code = get_ai_fix(error_log, code)

            print("Applying fix...")
            apply_fix(target_file, fixed_code)

            if attempt == max_retries:
                print("Reached max retries. Failed to fix the code.")
                sys.exit(1)

if __name__ == "__main__":
    main()

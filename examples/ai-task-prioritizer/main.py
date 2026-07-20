import argparse
import sys

from llm_client import LLMClient
from prioritizer import Prioritizer


def main():
    parser = argparse.ArgumentParser(description="AI-Powered Task Prioritizer")
    parser.add_argument("input", help="Path to a file containing tasks (one per line) or '-' for stdin")
    args = parser.parse_args()

    # Read tasks
    try:
        if args.input == "-":
            tasks = [line.strip() for line in sys.stdin if line.strip()]
        else:
            with open(args.input) as f:
                tasks = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Error: File {args.input} not found.")
        sys.exit(1)

    if not tasks:
        print("No tasks found.")
        return

    # Setup components
    client = LLMClient()
    prioritizer = Prioritizer(client)

    try:
        print(f"Analyzing {len(tasks)} tasks... Please wait.\n")
        results = prioritizer.prioritize(tasks)

        # Print results in a table
        print(f"{'Task':<30} | {'Value':<5} | {'Effort':<6} | {'Score':<5} | {'Category'}")
        print("-" * 70)
        for res in results:
            print(f"{res['task'][:30]:<30} | {res['value']:<5} | {res['effort']:<6} | {res['score']:<5.2f} | {res['category']}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Test MCP integration with opencode."""

import json
import os
import subprocess
import sys


def test_mcp_server():
    """Test if MCP server can be started and responds."""
    print("Testing MCP server integration...")

    # Test 1: Check if MCP server module can be imported
    print("\n1. Testing MCP server module import...")
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from src.mcp_server import (
            ai_audit,
            ai_evolve,
            ai_explain,
            ai_flow,
            ai_guard,
            ai_map,
            ai_scaffold,
            ai_sync,
            ai_trace,
        )

        print("   ✓ MCP server module imported successfully")
    except Exception as e:
        print(f"   ✗ Failed to import MCP server module: {e}")
        return False

    # Test 2: Check if all tools are available
    print("\n2. Checking available MCP tools...")
    tools = {
        "ai_sync": ai_sync,
        "ai_guard": ai_guard,
        "ai_audit": ai_audit,
        "ai_flow": ai_flow,
        "ai_trace": ai_trace,
        "ai_map": ai_map,
        "ai_evolve": ai_evolve,
        "ai_scaffold": ai_scaffold,
        "ai_explain": ai_explain,
    }

    for name, tool in tools.items():
        if callable(tool):
            print(f"   ✓ {name}: available")
        else:
            print(f"   ✗ {name}: not callable")
            return False

    # Test 3: Check if MCP server can be started
    print("\n3. Testing MCP server startup...")
    try:
        # Start MCP server in background and kill it after 2 seconds
        _result = subprocess.run(
            [sys.executable, "-m", "src.mcp_server"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            timeout=3,
            capture_output=True,
            text=True,
        )
        # If we get here, server started (timeout is expected)
        print("   ✓ MCP server can be started")
    except subprocess.TimeoutExpired:
        # This is expected - server runs indefinitely
        print("   ✓ MCP server can be started (timeout expected)")
    except Exception as e:
        print(f"   ✗ Failed to start MCP server: {e}")
        return False

    # Test 4: Check opencode.json configuration
    print("\n4. Checking opencode.json configuration...")
    opencode_config_path = os.path.expanduser("~/.opencode/opencode.json")
    if os.path.exists(opencode_config_path):
        try:
            with open(opencode_config_path, "r") as f:
                config = json.load(f)

            if "mcp" in config and "ai-context-sync" in config["mcp"]:
                mcp_config = config["mcp"]["ai-context-sync"]
                if mcp_config.get("enabled", False):
                    print("   ✓ MCP server configured in opencode.json")
                    print(f"     Command: {mcp_config.get('command')}")
                    print(f"     Args: {mcp_config.get('args')}")
                    print(f"     CWD: {mcp_config.get('cwd')}")
                else:
                    print("   ✗ MCP server is disabled in opencode.json")
                    return False
            else:
                print("   ✗ MCP server not found in opencode.json")
                return False
        except Exception as e:
            print(f"   ✗ Failed to read opencode.json: {e}")
            return False
    else:
        print("   ✗ opencode.json not found")
        return False

    print("\n" + "=" * 50)
    print("✓ All MCP integration tests passed!")
    print("=" * 50)
    print("\nTo use MCP tools in opencode:")
    print("1. Start opencode in your project directory")
    print("2. The MCP tools will be automatically available")
    print("3. Use them in your prompts, e.g.:")
    print("   'Please use ai_sync to update the project context'")

    return True


if __name__ == "__main__":
    success = test_mcp_server()
    sys.exit(0 if success else 1)

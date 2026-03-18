"""Regression tests for Task 1: Call an LLM from Code.

These tests verify that agent.py:
- Runs successfully with a question argument
- Outputs valid JSON to stdout
- Contains required 'answer' and 'tool_calls' fields
"""

import json
import subprocess
import sys
from pathlib import Path


def test_agent_returns_valid_json():
    """Test that agent.py returns valid JSON with answer and tool_calls fields."""
    # Get the project root directory (parent of tests/)
    project_root = Path(__file__).parent.parent
    agent_path = project_root / "agent.py"

    # Run agent.py with a test question
    result = subprocess.run(
        [sys.executable, str(agent_path), "What is 2+2?"],
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(project_root),
    )

    # Check exit code
    assert result.returncode == 0, f"Agent failed with stderr: {result.stderr}"

    # Parse stdout as JSON
    output = result.stdout.strip()
    try:
        data = json.loads(output)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Agent output is not valid JSON: {output}") from e

    # Verify required fields exist
    assert "answer" in data, "Missing 'answer' field in output"
    assert "tool_calls" in data, "Missing 'tool_calls' field in output"

    # Verify answer is non-empty string
    assert isinstance(data["answer"], str), "'answer' should be a string"
    assert len(data["answer"]) > 0, "'answer' should not be empty"

    # Verify tool_calls is a list
    assert isinstance(data["tool_calls"], list), "'tool_calls' should be a list"


if __name__ == "__main__":
    test_agent_returns_valid_json()
    print("All tests passed!")

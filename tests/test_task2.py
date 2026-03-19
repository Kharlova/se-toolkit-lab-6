"""Regression tests for Task 2: The Documentation Agent.

These tests verify that agent.py:
- Executes tool calls (read_file, list_files)
- Returns valid JSON with answer, source, and tool_calls fields
- Correctly navigates the wiki to find answers
"""

import json
import subprocess
import sys
from pathlib import Path


def run_agent(question: str) -> dict:
    """Run agent.py with a question and return the parsed JSON output."""
    # Project root is two levels up from tests directory
    project_root = Path(__file__).parent.parent
    agent_path = project_root / "agent.py"

    result = subprocess.run(
        [sys.executable, str(agent_path), question],
        capture_output=True,
        text=True,
        timeout=120,
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

    return data


def test_agent_returns_valid_json_with_source():
    """Test that agent.py returns valid JSON with answer, source, and tool_calls fields."""
    data = run_agent("What is 2+2?")

    # Verify required fields exist
    assert "answer" in data, "Missing 'answer' field in output"
    assert "source" in data, "Missing 'source' field in output"
    assert "tool_calls" in data, "Missing 'tool_calls' field in output"

    # Verify answer is non-empty string
    assert isinstance(data["answer"], str), "'answer' should be a string"
    assert len(data["answer"]) > 0, "'answer' should not be empty"

    # Verify tool_calls is a list
    assert isinstance(data["tool_calls"], list), "'tool_calls' should be a list"


def test_read_file_tool():
    """Test that the agent uses read_file tool to answer wiki questions."""
    data = run_agent("How do you resolve a merge conflict?")

    # Verify tool_calls is not empty (agent should use tools)
    assert len(data["tool_calls"]) > 0, "Expected agent to use tools for wiki question"

    # Verify read_file was used
    tool_names = [call["tool"] for call in data["tool_calls"]]
    assert "read_file" in tool_names, "Expected read_file in tool_calls"

    # Verify source contains wiki file reference
    assert "wiki/" in data["source"] or any(
        "wiki/" in str(call.get("args", {}).get("path", ""))
        for call in data["tool_calls"]
    ), "Expected source to reference wiki file"


def test_list_files_tool():
    """Test that the agent uses list_files tool to discover wiki files."""
    data = run_agent("What files are in the wiki?")

    # Verify tool_calls is not empty (agent should use tools)
    assert len(data["tool_calls"]) > 0, "Expected agent to use tools for wiki question"

    # Verify list_files was used
    tool_names = [call["tool"] for call in data["tool_calls"]]
    assert "list_files" in tool_names, "Expected list_files in tool_calls"

    # Verify the tool was called with wiki path
    list_files_calls = [
        call for call in data["tool_calls"]
        if call["tool"] == "list_files"
    ]
    assert any(
        "wiki" in call.get("args", {}).get("path", "")
        for call in list_files_calls
    ), "Expected list_files to be called with wiki path"


if __name__ == "__main__":
    test_agent_returns_valid_json_with_source()
    print("Test 1 passed: Valid JSON with source")

    test_read_file_tool()
    print("Test 2 passed: read_file tool")

    test_list_files_tool()
    print("Test 3 passed: list_files tool")

    print("All tests passed!")

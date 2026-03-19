"""Regression tests for Task 3: The System Agent.

These tests verify that agent.py:
- Executes query_api tool for data-dependent questions
- Correctly selects tools based on question type (wiki vs API)
- Returns valid JSON with answer, source, and tool_calls fields
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


def test_query_api_for_item_count():
    """Test that the agent uses query_api to answer data-dependent questions.
    
    Question: "How many items are in the database?"
    Expected: Agent should call query_api with GET /items/
    """
    data = run_agent("How many items are in the database?")

    # Verify tool_calls is not empty (agent should use tools)
    assert len(data["tool_calls"]) > 0, "Expected agent to use tools for data question"

    # Verify query_api was used
    tool_names = [call["tool"] for call in data["tool_calls"]]
    assert "query_api" in tool_names, "Expected query_api in tool_calls for item count question"

    # Verify the answer contains a number
    answer = data.get("answer", "")
    import re
    numbers = re.findall(r"\d+", answer)
    assert len(numbers) > 0, "Expected answer to contain a number for item count question"


def test_read_file_for_framework_question():
    """Test that the agent uses read_file to answer source code questions.
    
    Question: "What Python web framework does this project use?"
    Expected: Agent should call read_file to check source code
    """
    data = run_agent("What Python web framework does this project's backend use?")

    # Verify tool_calls is not empty (agent should use tools)
    assert len(data["tool_calls"]) > 0, "Expected agent to use tools for source code question"

    # Verify read_file was used (not query_api for source code questions)
    tool_names = [call["tool"] for call in data["tool_calls"]]
    assert "read_file" in tool_names, "Expected read_file in tool_calls for framework question"

    # Verify the answer mentions FastAPI
    answer = data.get("answer", "").lower()
    assert "fastapi" in answer, "Expected answer to mention FastAPI framework"


if __name__ == "__main__":
    test_query_api_for_item_count()
    print("Test 1 passed: query_api for item count")

    test_read_file_for_framework_question()
    print("Test 2 passed: read_file for framework question")

    print("All Task 3 tests passed!")

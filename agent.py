#!/usr/bin/env python3
"""
Agent CLI - Calls an LLM with tools and returns a structured JSON answer.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON to stdout: {"answer": "...", "source": "...", "tool_calls": [...]}
    Debug output goes to stderr.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx


# Maximum number of tool calls per question
MAX_TOOL_CALLS = 10

# Project root directory
PROJECT_ROOT = Path(__file__).parent


def load_env_file(env_path: Path) -> dict[str, str]:
    """Load environment variables from a .env file."""
    env_vars = {}
    if env_path.exists():
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                env_vars[key.strip()] = value.strip()
    return env_vars


def load_config() -> dict[str, str]:
    """Load LLM configuration from .env.agent.secret."""
    env_path = PROJECT_ROOT / ".env.agent.secret"

    env_vars = load_env_file(env_path)

    config = {
        "api_key": env_vars.get("LLM_API_KEY", ""),
        "api_base": env_vars.get("LLM_API_BASE", ""),
        "model": env_vars.get("LLM_MODEL", "qwen3-coder-plus"),
    }

    return config


def get_tool_schemas() -> list[dict]:
    """Return the tool schemas for LLM function calling."""
    return [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read the contents of a file from the project repository",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative path from project root (e.g., 'wiki/git-workflow.md')"
                        }
                    },
                    "required": ["path"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List files and directories at a given path",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Relative directory path from project root (e.g., 'wiki')"
                        }
                    },
                    "required": ["path"]
                }
            }
        }
    ]


def validate_path(path: str) -> Path | None:
    """
    Validate that a path is within the project root.
    Returns the resolved absolute path if valid, None otherwise.
    """
    # Reject absolute paths
    if Path(path).is_absolute():
        return None

    # Construct the full path
    full_path = (PROJECT_ROOT / path).resolve()

    # Ensure the path is within project root
    try:
        full_path.relative_to(PROJECT_ROOT.resolve())
        return full_path
    except ValueError:
        return None


def read_file(path: str) -> str:
    """
    Read a file from the project repository.

    Args:
        path: Relative path from project root

    Returns:
        File contents as string, or error message
    """
    validated = validate_path(path)
    if validated is None:
        return f"Error: Path '{path}' is not allowed (security restriction)"

    if not validated.exists():
        return f"Error: File '{path}' does not exist"

    if not validated.is_file():
        return f"Error: '{path}' is not a file"

    try:
        return validated.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading file: {e}"


def list_files(path: str) -> str:
    """
    List files and directories at a given path.

    Args:
        path: Relative directory path from project root

    Returns:
        Newline-separated listing, or error message
    """
    validated = validate_path(path)
    if validated is None:
        return f"Error: Path '{path}' is not allowed (security restriction)"

    if not validated.exists():
        return f"Error: Directory '{path}' does not exist"

    if not validated.is_dir():
        return f"Error: '{path}' is not a directory"

    try:
        entries = sorted(validated.iterdir())
        lines = []
        for entry in entries:
            suffix = "/" if entry.is_dir() else ""
            lines.append(f"{entry.name}{suffix}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error listing directory: {e}"


def execute_tool(tool_name: str, args: dict) -> str:
    """
    Execute a tool and return the result.

    Args:
        tool_name: Name of the tool to execute
        args: Tool arguments

    Returns:
        Tool result as string
    """
    if tool_name == "read_file":
        return read_file(args.get("path", ""))
    elif tool_name == "list_files":
        return list_files(args.get("path", ""))
    else:
        return f"Error: Unknown tool '{tool_name}'"


SYSTEM_PROMPT = """You are a documentation agent that answers questions by reading the project wiki.

You have access to two tools:
- `list_files`: List files and directories at a given path
- `read_file`: Read the contents of a file

To answer a question:
1. Use `list_files` to discover wiki files if you're unsure where to look
2. Use `read_file` to read specific files and find the answer
3. Always include a source reference in your answer (file path + section anchor like `wiki/git-workflow.md#resolving-merge-conflicts`)
4. Make at most 10 tool calls

When you have found the answer, respond with a clear, concise answer and include the source reference.
"""


async def call_llm(
    config: dict[str, str],
    messages: list[dict],
    tools: list[dict] | None = None
) -> dict:
    """
    Call the LLM API and return the response.

    Args:
        config: LLM configuration
        messages: Conversation messages
        tools: Optional tool schemas for function calling

    Returns:
        LLM response data
    """
    url = f"{config['api_base']}/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config['api_key']}",
    }

    payload = {
        "model": config["model"],
        "messages": messages,
    }

    if tools:
        payload["tools"] = tools

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()


async def run_agent(config: dict[str, str], question: str) -> dict:
    """
    Run the agentic loop.

    Args:
        config: LLM configuration
        question: User's question

    Returns:
        Result dict with answer, source, and tool_calls
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question}
    ]

    tools = get_tool_schemas()
    tool_calls_log = []
    tool_call_count = 0

    print(f"Starting agentic loop for question: {question}", file=sys.stderr)

    while tool_call_count < MAX_TOOL_CALLS:
        print(f"Loop iteration {tool_call_count + 1}, calling LLM...", file=sys.stderr)

        response_data = await call_llm(config, messages, tools)

        if "choices" not in response_data or len(response_data["choices"]) == 0:
            raise ValueError("No choices in LLM response")

        choice = response_data["choices"][0]
        message = choice["message"]

        # Check for tool calls
        tool_calls = message.get("tool_calls", [])

        if not tool_calls:
            # No tool calls, LLM provided a final answer
            print("LLM provided final answer, no tool calls", file=sys.stderr)
            answer = message.get("content", "")

            # Try to extract source from the answer
            source = extract_source(answer)

            return {
                "answer": answer,
                "source": source,
                "tool_calls": tool_calls_log
            }

        # Execute tool calls
        print(f"LLM requested {len(tool_calls)} tool call(s)", file=sys.stderr)

        for tool_call in tool_calls:
            tool_call_count += 1
            if tool_call_count > MAX_TOOL_CALLS:
                print(f"Reached maximum tool calls ({MAX_TOOL_CALLS})", file=sys.stderr)
                break

            function = tool_call["function"]
            tool_name = function["name"]
            args = json.loads(function["arguments"])

            print(f"Executing tool: {tool_name} with args: {args}", file=sys.stderr)

            result = execute_tool(tool_name, args)

            # Log the tool call
            tool_calls_log.append({
                "tool": tool_name,
                "args": args,
                "result": result
            })

            # Append tool result to messages
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.get("id", f"{tool_name}_{tool_call_count}"),
                "name": tool_name,
                "content": result
            })

    # Reached maximum tool calls
    print("Maximum tool calls reached, returning best answer", file=sys.stderr)

    # Make one final call to get the answer
    messages.append({
        "role": "user",
        "content": "Please provide your final answer based on the information gathered."
    })

    response_data = await call_llm(config, messages, None)
    answer = response_data["choices"][0]["message"].get("content", "")
    source = extract_source(answer)

    return {
        "answer": answer,
        "source": source,
        "tool_calls": tool_calls_log
    }


def extract_source(answer: str) -> str:
    """
    Try to extract a source reference from the answer.
    Looks for patterns like wiki/file.md or wiki/file.md#section

    Args:
        answer: The LLM's answer text

    Returns:
        Source reference or empty string if not found
    """
    import re

    # Look for wiki file references
    pattern = r'(wiki/[\w\-\.]+(?:#[\w\-]+)?)'
    match = re.search(pattern, answer)

    if match:
        return match.group(1)

    return ""


def main() -> int:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: uv run agent.py \"Your question here\"", file=sys.stderr)
        return 1

    question = sys.argv[1]

    print(f"Question: {question}", file=sys.stderr)

    try:
        config = load_config()

        if not config["api_key"]:
            print("Error: LLM_API_KEY not set in .env.agent.secret", file=sys.stderr)
            return 1

        if not config["api_base"]:
            print("Error: LLM_API_BASE not set in .env.agent.secret", file=sys.stderr)
            return 1

        print(f"Using model: {config['model']}", file=sys.stderr)

        result = asyncio.run(run_agent(config, question))

        print(json.dumps(result))

        return 0

    except httpx.HTTPStatusError as e:
        print(f"HTTP error: {e.response.status_code}", file=sys.stderr)
        print(f"Response: {e.response.text}", file=sys.stderr)
        return 1
    except httpx.RequestError as e:
        print(f"Request error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

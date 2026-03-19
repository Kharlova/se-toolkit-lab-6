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
    """Load LLM and API configuration from environment files."""
    agent_env_path = PROJECT_ROOT / ".env.agent.secret"
    docker_env_path = PROJECT_ROOT / ".env.docker.secret"

    agent_env_vars = load_env_file(agent_env_path)
    docker_env_vars = load_env_file(docker_env_path)

    config = {
        # LLM configuration
        "api_key": agent_env_vars.get("LLM_API_KEY", ""),
        "api_base": agent_env_vars.get("LLM_API_BASE", ""),
        "model": agent_env_vars.get("LLM_MODEL", "qwen3-coder-plus"),
        # Backend API configuration
        "lms_api_key": docker_env_vars.get("LMS_API_KEY", ""),
        "agent_api_base_url": os.environ.get(
            "AGENT_API_BASE_URL",
            agent_env_vars.get("AGENT_API_BASE_URL", "http://localhost:42001")
        ),
    }

    return config


def get_tool_schemas() -> list[dict]:
    """Return the tool schemas for LLM function calling."""
    return [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read the contents of a file from the project repository. Use for wiki documentation and source code questions.",
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
                "description": "List files and directories at a given path. Use to discover files in a directory.",
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
        },
        {
            "type": "function",
            "function": {
                "name": "query_api",
                "description": "Query the backend API. Use for data-dependent questions like item counts, scores, analytics, or to check API status codes. Returns JSON with status_code and body. Set auth=false to test unauthenticated requests.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "method": {
                            "type": "string",
                            "description": "HTTP method (GET, POST, PUT, DELETE, etc.)"
                        },
                        "path": {
                            "type": "string",
                            "description": "API path (e.g., '/items/', '/analytics/completion-rate?lab=lab-01')"
                        },
                        "body": {
                            "type": "string",
                            "description": "Optional JSON request body for POST/PUT requests"
                        },
                        "auth": {
                            "type": "boolean",
                            "description": "Whether to include authentication (default: true). Set to false to test unauthenticated requests."
                        }
                    },
                    "required": ["method", "path"]
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


def query_api(method: str, path: str, body: str | None = None, auth: bool = True) -> str:
    """
    Query the backend API with optional authentication.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE, etc.)
        path: API path (e.g., '/items/', '/analytics/completion-rate?lab=lab-01')
        body: Optional JSON request body for POST/PUT requests
        auth: Whether to include authentication (default: True)

    Returns:
        JSON string with status_code and body, or error message
    """
    config = load_config()
    lms_api_key = config.get("lms_api_key", "")
    base_url = config.get("agent_api_base_url", "http://localhost:42002")

    # Build full URL
    url = f"{base_url.rstrip('/')}{path}"

    headers = {
        "Content-Type": "application/json",
    }
    
    # Only add authentication if requested
    if auth:
        if not lms_api_key:
            return '{"status_code": 500, "body": {"error": "LMS_API_KEY not configured"}}'
        headers["Authorization"] = f"Bearer {lms_api_key}"

    try:
        # Use sync httpx for simplicity in tool execution
        with httpx.Client(timeout=30.0) as client:
            if method.upper() == "GET":
                response = client.get(url, headers=headers)
            elif method.upper() == "POST":
                response = client.post(url, headers=headers, json=json.loads(body) if body else None)
            elif method.upper() == "PUT":
                response = client.put(url, headers=headers, json=json.loads(body) if body else None)
            elif method.upper() == "DELETE":
                response = client.delete(url, headers=headers)
            else:
                return f'{{"status_code": 400, "body": {{"error": "Unsupported method: {method}"}}}}'

            # Try to parse response as JSON
            try:
                response_body = response.json()
            except json.JSONDecodeError:
                response_body = response.text

            return json.dumps({
                "status_code": response.status_code,
                "body": response_body
            })
    except httpx.HTTPStatusError as e:
        return json.dumps({
            "status_code": e.response.status_code,
            "body": {"error": str(e)}
        })
    except httpx.RequestError as e:
        return json.dumps({
            "status_code": 0,
            "body": {"error": f"Request error: {e}"}
        })
    except json.JSONDecodeError as e:
        return json.dumps({
            "status_code": 400,
            "body": {"error": f"Invalid JSON body: {e}"}
        })
    except Exception as e:
        return json.dumps({
            "status_code": 500,
            "body": {"error": str(e)}
        })


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
    elif tool_name == "query_api":
        return query_api(
            args.get("method", "GET"),
            args.get("path", ""),
            args.get("body"),
            args.get("auth", True)
        )
    else:
        return f"Error: Unknown tool '{tool_name}'"


SYSTEM_PROMPT = """You are a documentation and system agent that answers questions by reading the project wiki, source code, and querying the backend API.

You have access to three tools:
- `list_files`: List files and directories at a given path. Use to discover files in a directory.
- `read_file`: Read the contents of a file. Use for wiki documentation and source code questions.
- `query_api`: Query the backend API. Use for data-dependent questions (item counts, scores, analytics) or to check API responses (status codes, error messages). Set auth=false to test unauthenticated requests.

To answer a question:
1. For wiki/documentation questions: Use `list_files` to discover wiki files, then `read_file` to read specific files. Wiki files are in the `wiki/` directory.
2. For source code questions: Backend source code is in `backend/app/` directory. Routers are in `backend/app/routers/`. Use `list_files` to discover files, then `read_file` to read them.
3. For data-dependent questions (e.g., "how many items", "what is the score"): Use `query_api` to query the backend.
4. For API behavior questions (e.g., status codes, errors): Use `query_api` to make the actual request.
5. For bug diagnosis questions: First query the API to see the error, then read the source code to find the bug location. Always include the source file path in your answer.
6. Always include a source reference in your answer when reading files (file path + section anchor like `wiki/git-workflow.md#resolving-merge-conflicts`). For API queries about bugs, also mention the source file where the bug is located.
7. Make at most 10 tool calls.

When you have found the answer, respond with a clear, concise answer. Include the source reference for file-based answers.
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
        "max_tokens": 2048,
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

        # First, append the assistant's message with tool_calls
        assistant_message = {
            "role": "assistant",
            "content": None,
            "tool_calls": tool_calls
        }
        messages.append(assistant_message)

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
    Looks for patterns like wiki/file.md, backend/app/*.py, or file paths.

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

    # Look for backend source file references
    pattern = r'(backend/app/[\w\-\.\/]+\.(?:py|md))'
    match = re.search(pattern, answer)

    if match:
        return match.group(1)

    # Look for /app/backend/... paths (from error messages)
    pattern = r'(/app/backend/[\w\-\.\/]+)'
    match = re.search(pattern, answer)

    if match:
        # Convert to relative path
        path = match.group(1).replace('/app/backend/', 'backend/')
        return path

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

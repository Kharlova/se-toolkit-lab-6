# Agent Architecture

## Overview

This agent is a Python CLI that calls an LLM with tools and returns structured JSON responses. It implements an agentic loop that allows the LLM to discover and read project documentation to answer questions.

## LLM Provider

- **Provider**: Qwen Code API (self-hosted via `qwen-code-oai-proxy`)
- **Model**: `qwen3-coder-plus`
- **API Type**: OpenAI-compatible chat completions API with function calling
- **Endpoint**: `http://<vm-ip>:42005/v1`

### Why Qwen Code API?

- 1000 free requests per day
- Works from Russia
- No credit card required
- OpenAI-compatible API with tool calling support

## Architecture

### High-Level Flow

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐     ┌─────────────┐
│   User      │────▶│   agent.py   │────▶│  Qwen Code      │────▶│   LLM       │
│  (CLI arg)  │     │  (CLI tool)  │     │  Proxy (VM)     │     │  (Cloud)    │
└─────────────┘     └──────────────┘     └─────────────────┘     └─────────────┘
                           │                      │
                           │◀─────────────────────┤
                           │  tool_calls          │
                           │                      │
                           │◀─────────────────────┤
                           │  execute tools       │
                           │  (read_file,         │
                           │   list_files)        │
                           │                      │
                           │◀─────────────────────┤
                           │  final answer        │
                           ▼                      │
                    ┌──────────────┐              │
                    │  JSON output │              │
                    │  {answer,    │              │
                    │   source,    │              │
                    │   tool_calls}│              │
                    └──────────────┘              │
                                          ┌───────┴────────┐
                                          │  Project Wiki  │
                                          │  (wiki/*.md)   │
                                          └────────────────┘
```

### Agentic Loop

The agent implements a ReAct-style agentic loop:

1. **Send question**: User's question + system prompt sent to LLM with tool definitions
2. **LLM decides**: LLM responds with either:
   - `tool_calls`: Execute tools, append results, repeat
   - Text answer: Return final JSON response
3. **Loop limit**: Maximum 10 tool calls per question

```
┌─────────────────────────────────────────────────────────────┐
│                    Agentic Loop                             │
│                                                             │
│  1. Send messages + tools to LLM                            │
│  2. Receive response                                        │
│  3. If tool_calls:                                          │
│     - Execute each tool                                     │
│     - Append results as tool messages                       │
│     - Go to step 1                                          │
│  4. If text answer:                                         │
│     - Extract answer and source                             │
│     - Return JSON                                           │
│     - Exit                                                  │
└─────────────────────────────────────────────────────────────┘
```

## Components

### `agent.py`

The main CLI program that:

1. **Parses input**: Takes a question as the first command-line argument
2. **Loads configuration**: Reads LLM settings from `.env.agent.secret`
3. **Implements tools**: `read_file` and `list_files` with path security
4. **Runs agentic loop**: Executes tool calls and feeds results back to LLM
5. **Formats output**: Returns JSON with `answer`, `source`, and `tool_calls`

### Tools

#### `read_file`

Reads a file from the project repository.

- **Parameters**: `path` (string) — relative path from project root
- **Returns**: File contents as string, or error message
- **Security**: Validates path stays within project root (no `../` traversal)

#### `list_files`

Lists files and directories at a given path.

- **Parameters**: `path` (string) — relative directory path from project root
- **Returns**: Newline-separated listing, or error message
- **Security**: Validates path stays within project root

### System Prompt

The system prompt instructs the LLM to:

1. Use `list_files` to discover wiki files when unsure about file locations
2. Use `read_file` to read specific files and find answers
3. Always include a source reference (file path + section anchor)
4. Make at most 10 tool calls
5. Return a concise answer with the source

### Configuration (`.env.agent.secret`)

```bash
# LLM API key (from qwen-code-oai-proxy/.env)
LLM_API_KEY=my-secret-qwen-key

# API base URL
LLM_API_BASE=http://<vm-ip>:42005/v1

# Model name
LLM_MODEL=qwen3-coder-plus
```

## Usage

### Basic Usage

```bash
uv run agent.py "How do you resolve a merge conflict?"
```

### Output Format

```json
{
  "answer": "Edit the conflicting file, choose which changes to keep, then stage and commit.",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": "git-workflow.md\n..."
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-workflow.md"},
      "result": "..."
    }
  ]
}
```

- `answer`: The LLM's final answer
- `source`: Wiki section reference (file path + optional section anchor)
- `tool_calls`: Array of all tool calls made, each with `tool`, `args`, and `result`

### Debug Output

All debug and progress output goes to **stderr**, not stdout:

```
Question: How do you resolve a merge conflict?    # stderr
Using model: qwen3-coder-plus                     # stderr
Starting agentic loop...                          # stderr
Loop iteration 1, calling LLM...                  # stderr
LLM requested 1 tool call(s)                      # stderr
Executing tool: list_files with args: {...}       # stderr
...
{"answer": "...", "source": "...", "tool_calls": [...]}  # stdout
```

## Dependencies

- `httpx`: Async HTTP client for API calls
- Python 3.12+

## Error Handling

The agent handles the following error cases:

- **Missing arguments**: Shows usage message
- **Missing configuration**: Reports missing API key or base URL
- **HTTP errors**: Reports status code and response body
- **Network errors**: Reports connection issues
- **LLM errors**: Reports API errors gracefully
- **Path security**: Rejects paths outside project root
- **Tool errors**: Returns error message as tool result

All errors are logged to stderr, and the agent exits with a non-zero exit code on failure.

## Testing

### Manual Testing

Run the agent with different questions:

```bash
# Test read_file tool
uv run agent.py "How do you resolve a merge conflict?"

# Test list_files tool
uv run agent.py "What files are in the wiki?"

# Test multi-step reasoning
uv run agent.py "How do you set up the Qwen Code API?"
```

### Automated Tests

Run the test suite:

```bash
uv run pytest tests/ -v
```

Tests verify:
- Task 1: Basic LLM calling with valid JSON output
- Task 2: Tool calling with `read_file` and `list_files`
- Task 2: Correct source extraction

## Security

The agent enforces path security for file operations:

1. **No absolute paths**: Tool arguments must be relative paths
2. **No path traversal**: `../` sequences are rejected
3. **Project root validation**: Resolved paths must be within project root
4. **UTF-8 encoding**: All file operations use UTF-8

## Future Extensions (Task 3)

In Task 3, you will extend this agent to:

1. **Add domain knowledge**: Connect to the backend LMS for course information
2. **Add more tools**: Implement tools for API queries, database lookups, etc.
3. **Improve reasoning**: Enhance the system prompt for better tool selection
4. **Add caching**: Cache frequently accessed files to reduce API calls

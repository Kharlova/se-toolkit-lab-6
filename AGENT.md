# Agent Architecture

## Overview

This agent is a Python CLI that calls an LLM with tools and returns structured JSON responses. It implements an agentic loop that allows the LLM to discover and read project documentation, source code, and query the backend API to answer questions.

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
                           │   list_files,        │
                           │   query_api)         │
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
                                          │  Source Code   │
                                          │  (backend/app) │
                                          └────────────────┘
                                                 │
                                                 │
                                    ┌────────────┴───────────┐
                                    │   Backend API          │
                                    │   (items, analytics)   │
                                    └────────────────────────┘
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
2. **Loads configuration**: Reads LLM settings from `.env.agent.secret` and backend API key from `.env.docker.secret`
3. **Implements tools**: `read_file`, `list_files`, and `query_api` with path security and authentication
4. **Runs agentic loop**: Executes tool calls and feeds results back to LLM
5. **Formats output**: Returns JSON with `answer`, `source`, and `tool_calls`

### Tools

#### `read_file`

Reads a file from the project repository.

- **Parameters**: `path` (string) — relative path from project root
- **Returns**: File contents as string, or error message
- **Security**: Validates path stays within project root (no `../` traversal)
- **Use case**: Wiki documentation, source code files

#### `list_files`

Lists files and directories at a given path.

- **Parameters**: `path` (string) — relative directory path from project root
- **Returns**: Newline-separated listing, or error message
- **Security**: Validates path stays within project root
- **Use case**: Discovering files in a directory

#### `query_api`

Queries the backend API with authentication.

- **Parameters**: 
  - `method` (string) — HTTP method (GET, POST, PUT, DELETE)
  - `path` (string) — API path (e.g., `/items/`, `/analytics/completion-rate?lab=lab-01`)
  - `body` (string, optional) — JSON request body for POST/PUT requests
- **Returns**: JSON string with `status_code` and `body`
- **Authentication**: Uses `LMS_API_KEY` from `.env.docker.secret` via `Authorization: Bearer` header
- **Base URL**: Configured via `AGENT_API_BASE_URL` environment variable (default: `http://localhost:42001`)
- **Use case**: Data-dependent questions (item counts, scores, analytics), API status code checks

### System Prompt

The system prompt instructs the LLM to:

1. Use `list_files` to discover wiki files when unsure about file locations
2. Use `read_file` to read specific wiki or source code files
3. Use `query_api` for data-dependent questions (item counts, scores) or API behavior questions (status codes, errors)
4. Always include a source reference for file-based answers (file path + section anchor)
5. Make at most 10 tool calls
6. Return a concise answer with the source

### How the LLM Decides Between Tools

The LLM uses the tool descriptions and system prompt to decide which tool to use:

| Question Type | Example | Expected Tool |
|--------------|---------|---------------|
| Wiki lookup | "How do you protect a branch?" | `read_file` |
| Source code lookup | "What framework does the backend use?" | `read_file` |
| File discovery | "What API routers exist?" | `list_files` |
| Data query | "How many items are in the database?" | `query_api` |
| API status code | "What status code for unauthenticated request?" | `query_api` |
| Bug diagnosis | "Why does /analytics/completion-rate crash?" | `query_api` + `read_file` |

### Configuration

#### `.env.agent.secret` (LLM Configuration)

```bash
# LLM API key (from qwen-code-oai-proxy/.env)
LLM_API_KEY=my-secret-qwen-key

# API base URL
LLM_API_BASE=http://<vm-ip>:42005/v1

# Model name
LLM_MODEL=qwen3-coder-plus
```

#### `.env.docker.secret` (Backend API Configuration)

```bash
# Secret key used to authorize in the backend LMS API
LMS_API_KEY=set-it-to-something-and-remember-it
```

#### Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `LLM_API_KEY` | LLM provider API key | (required) |
| `LLM_API_BASE` | LLM API endpoint URL | (required) |
| `LLM_MODEL` | Model name | `qwen3-coder-plus` |
| `LMS_API_KEY` | Backend API key for `query_api` auth | (required for API queries) |
| `AGENT_API_BASE_URL` | Base URL for `query_api` | `http://localhost:42001` |

> **Note:** Two distinct keys: `LMS_API_KEY` (in `.env.docker.secret`) protects your backend endpoints. `LLM_API_KEY` (in `.env.agent.secret`) authenticates with your LLM provider. Don't mix them up.

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
# Test read_file tool (wiki questions)
uv run agent.py "How do you resolve a merge conflict?"

# Test list_files tool (file discovery)
uv run agent.py "What files are in the wiki?"

# Test query_api tool (data queries)
uv run agent.py "How many items are in the database?"

# Test query_api tool (status codes)
uv run agent.py "What status code for unauthenticated request?"

# Test multi-step reasoning
uv run agent.py "Why does /analytics/completion-rate crash for lab-99?"
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
- Task 3: Tool calling with `query_api` for data-dependent questions
- Task 3: Correct tool selection based on question type

### Benchmark Evaluation

Run the local benchmark to evaluate the agent against 10 questions:

```bash
uv run run_eval.py
```

The benchmark tests:
- Wiki lookup questions (branch protection, SSH connection)
- Source code questions (framework, router modules)
- Data-dependent questions (item count, scores)
- API behavior questions (status codes, error messages)
- Bug diagnosis questions (ZeroDivisionError, TypeError)
- Reasoning questions (request lifecycle, ETL idempotency)

## Security

The agent enforces path security for file operations:

1. **No absolute paths**: Tool arguments must be relative paths
2. **No path traversal**: `../` sequences are rejected
3. **Project root validation**: Resolved paths must be within project root
4. **UTF-8 encoding**: All file operations use UTF-8
5. **API key protection**: `LMS_API_KEY` is loaded from `.env.docker.secret`, never hardcoded

## Lessons Learned

### Tool Design

1. **Clear tool descriptions matter**: The LLM relies on tool descriptions to decide which tool to use. Vague descriptions lead to wrong tool selection. We improved descriptions by adding explicit use cases (e.g., "Use for data-dependent questions like item counts, scores, analytics").

2. **Parameter descriptions are critical**: For `query_api`, we initially had vague parameter descriptions. Adding examples like `/items/` and `/analytics/completion-rate?lab=lab-01` helped the LLM understand the expected format.

3. **System prompt guidance**: The system prompt needs explicit guidance on when to use each tool. We added a numbered list with specific scenarios for each tool type.

### API Integration

1. **Authentication handling**: The `query_api` tool needs to authenticate with `LMS_API_KEY`. We load this from `.env.docker.secret` to keep it separate from LLM credentials.

2. **Error responses**: When the API returns an error, we include both `status_code` and `body` in the response. This helps the LLM diagnose issues like 401 (unauthorized) vs 500 (server error).

3. **Query parameters**: The LLM learned to include query parameters in the path (e.g., `?lab=lab-01`) for endpoints that require them.

### Benchmark Iteration

1. **Multi-step questions**: Some questions require multiple tool calls (e.g., query API to see error, then read source code to find bug). The agentic loop handles this naturally.

2. **Source extraction**: For API-based answers, we don't require a file source. The `source` field is now optional for data-dependent questions.

3. **Timeout handling**: Some LLM calls can be slow. We set a 60-second timeout and limit tool calls to 10 per question.

### Final Evaluation Score

After iteration, the agent passes all 10 local benchmark questions:
- ✓ Wiki questions (branch protection, SSH connection)
- ✓ Source code questions (FastAPI framework, router modules)
- ✓ Data queries (item count via `/items/`)
- ✓ API status codes (401 for unauthenticated requests)
- ✓ Bug diagnosis (ZeroDivisionError in completion-rate, TypeError in top-learners)
- ✓ Reasoning questions (request lifecycle, ETL idempotency)

**Final Score: 10/10 passed**

# Agent Architecture

## Overview

This agent is a Python CLI that calls an LLM and returns structured JSON responses. It is the foundation for the more advanced agent you will build in Tasks 2-3.

## LLM Provider

- **Provider**: Qwen Code API (self-hosted via `qwen-code-oai-proxy`)
- **Model**: `qwen3-coder-plus`
- **API Type**: OpenAI-compatible chat completions API
- **Endpoint**: `http://<vm-ip>:42005/v1`

### Why Qwen Code API?

- 1000 free requests per day
- Works from Russia
- No credit card required
- OpenAI-compatible API

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐     ┌─────────────┐
│   User      │────▶│   agent.py   │────▶│  Qwen Code      │────▶│   LLM       │
│  (CLI arg)  │     │  (CLI tool)  │     │  Proxy (VM)     │     │  (Cloud)    │
└─────────────┘     └──────────────┘     └─────────────────┘     └─────────────┘
                           │
                           ▼
                    ┌──────────────┐
                    │  JSON output │
                    │  {answer,    │
                    │  tool_calls} │
                    └──────────────┘
```

## Components

### `agent.py`

The main CLI program that:

1. **Parses input**: Takes a question as the first command-line argument
2. **Loads configuration**: Reads LLM settings from `.env.agent.secret`
3. **Calls the LLM**: Sends an HTTP POST request to the `/v1/chat/completions` endpoint
4. **Formats output**: Returns a JSON object with `answer` and `tool_calls` fields

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
uv run agent.py "What is REST?"
```

### Output Format

```json
{"answer": "Representational State Transfer.", "tool_calls": []}
```

- `answer`: The LLM's response to the question
- `tool_calls`: Empty array for Task 1 (will be populated in Task 2)

### Debug Output

All debug and progress output goes to **stderr**, not stdout:

```
Question: What is REST?           # stderr
Using model: qwen3-coder-plus     # stderr
Calling LLM at http://...         # stderr
Token usage: {...}                # stderr
{"answer": "...", "tool_calls": []}  # stdout
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

All errors are logged to stderr, and the agent exits with a non-zero exit code on failure.

## Testing

Run the agent with a test question:

```bash
uv run agent.py "What is 2+2?"
```

Expected output:
- JSON with non-empty `answer` field
- Empty `tool_calls` array
- Exit code 0

## Future Extensions (Tasks 2-3)

In the next tasks, you will extend this agent to:

1. **Add tools**: Implement tool calling for actions like file operations, API queries, etc.
2. **Add agentic loop**: Implement a ReAct-style loop for multi-step reasoning
3. **Add domain knowledge**: Connect to the backend LMS for course information

# Task 1: Call an LLM from Code - Implementation Plan

## LLM Provider and Model

- **Provider**: Qwen Code API (self-hosted via qwen-code-oai-proxy)
- **Model**: `qwen3-coder-plus`
- **API Endpoint**: `http://10.93.26.70:42005/v1`
- **Authentication**: Bearer token (API key stored in `.env.agent.secret`)

## Architecture

The agent will be a simple Python CLI that:

1. **Parses command-line input** - takes a question as the first argument
2. **Loads configuration** - reads LLM settings from `.env.agent.secret`
3. **Calls the LLM** - sends a POST request to the OpenAI-compatible `/v1/chat/completions` endpoint
4. **Formats output** - returns a JSON response with `answer` and `tool_calls` fields

## Data Flow

```
User input (CLI arg) → agent.py → HTTP POST → Qwen Code Proxy → LLM → Response → JSON output
```

## Implementation Steps

1. **Setup**:
   - Create `.env.agent.secret` with LLM credentials
   - Install required dependencies (`httpx` for async HTTP requests)

2. **Create `agent.py`**:
   - Import dependencies: `sys`, `json`, `os`, `httpx`
   - Load environment variables from `.env.agent.secret`
   - Define async function to call LLM API
   - Parse CLI argument (question)
   - Call LLM and extract response
   - Output JSON to stdout with `answer` and `tool_calls` fields
   - Send debug output to stderr

3. **Error Handling**:
   - Handle network errors gracefully
   - Handle API errors (401, 429, 500)
   - Exit with code 0 on success, non-zero on failure

## Testing

- Create 1 regression test in `lab/tests/` that:
  - Runs `agent.py` as a subprocess with a test question
  - Parses stdout JSON
  - Verifies `answer` field exists and is non-empty
  - Verifies `tool_calls` field exists (will be empty array for Task 1)

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `plans/task-1.md` | Create | Implementation plan |
| `.env.agent.secret` | Create | LLM credentials |
| `agent.py` | Create | Main CLI program |
| `AGENT.md` | Create | Architecture documentation |
| `lab/tests/test_task1.py` | Create | Regression test |

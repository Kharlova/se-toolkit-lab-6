# Task 3: The System Agent - Implementation Plan

## Overview

This task extends the Task 2 documentation agent with a new `query_api` tool that allows the agent to query the deployed backend API. The agent will be able to answer:
- Static system facts (framework, ports, status codes)
- Data-dependent queries (item count, scores, completion rates)

## Implementation Plan

### 1. Environment Variables Configuration

The agent needs to read the following environment variables:

| Variable | Purpose | Source |
|----------|---------|--------|
| `LLM_API_KEY` | LLM provider API key | `.env.agent.secret` |
| `LLM_API_BASE` | LLM API endpoint URL | `.env.agent.secret` |
| `LLM_MODEL` | Model name | `.env.agent.secret` |
| `LMS_API_KEY` | Backend API key for `query_api` auth | `.env.docker.secret` |
| `AGENT_API_BASE_URL` | Base URL for `query_api` (default: `http://localhost:42002`) | Optional, defaults to localhost |

### 2. `query_api` Tool Schema

Add a new tool to `get_tool_schemas()`:

```python
{
    "type": "function",
    "function": {
        "name": "query_api",
        "description": "Query the backend API with authentication. Use for data-dependent questions like item counts, scores, analytics.",
        "parameters": {
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "description": "HTTP method (GET, POST, etc.)"
                },
                "path": {
                    "type": "string",
                    "description": "API path (e.g., '/items/', '/analytics/completion-rate')"
                },
                "body": {
                    "type": "string",
                    "description": "Optional JSON request body for POST/PUT requests"
                }
            },
            "required": ["method", "path"]
        }
    }
}
```

### 3. `query_api` Tool Implementation

Implement the `query_api` function:
- Read `LMS_API_KEY` from `.env.docker.secret`
- Read `AGENT_API_BASE_URL` from environment (default: `http://localhost:42002`)
- Make HTTP request with `X-API-Key` header
- Return JSON string with `status_code` and `body`

```python
def query_api(method: str, path: str, body: str | None = None) -> str:
    """Query the backend API with authentication."""
    # Load LMS_API_KEY from .env.docker.secret
    # Build URL from AGENT_API_BASE_URL + path
    # Make request with X-API-Key header
    # Return JSON string with status_code and body
```

### 4. Update System Prompt

Update the system prompt to guide the LLM on when to use each tool:
- `read_file` / `list_files`: For wiki documentation and source code questions
- `query_api`: For data-dependent questions (item counts, scores, analytics) and system facts (status codes, API responses)

### 5. Update `execute_tool()`

Add handling for the new `query_api` tool in the `execute_tool()` function.

### 6. Update `AGENT.md`

Document:
- The new `query_api` tool and its authentication
- How the LLM decides between wiki and system tools
- Lessons learned from the benchmark
- Final eval score

### 7. Add Tests

Add 2 regression tests:
1. Test that system questions use `query_api` (e.g., "How many items are in the database?")
2. Test that source code questions use `read_file` (e.g., "What framework does the backend use?")

## Benchmark Questions Analysis

| # | Question | Required Tool(s) | Expected Answer |
|---|----------|------------------|-----------------|
| 0 | Wiki: protect a branch | `read_file` | `branch`, `protect` |
| 1 | Wiki: SSH connection | `read_file` | `ssh` / `key` / `connect` |
| 2 | Framework from source | `read_file` | `FastAPI` |
| 3 | API router modules | `list_files` | `items`, `interactions`, `analytics`, `pipeline` |
| 4 | Items in database | `query_api` | number > 0 |
| 5 | Status code without auth | `query_api` | `401` / `403` |
| 6 | `/analytics/completion-rate` bug | `query_api`, `read_file` | `ZeroDivisionError` |
| 7 | `/analytics/top-learners` bug | `query_api`, `read_file` | `TypeError` / `None` |
| 8 | Request lifecycle | `read_file` | ≥4 hops: Caddy → FastAPI → auth → router → ORM → PostgreSQL |
| 9 | ETL idempotency | `read_file` | `external_id` check, duplicates skipped |

## Initial Score and Iteration Strategy

### First Run Results

Initial run showed issues with:
1. **Question 6 (status code without auth)**: Agent didn't actually test unauthenticated requests - assumed endpoint was public.
   - **Fix**: Added `auth` parameter to `query_api` tool to allow testing unauthenticated requests.

2. **Question 7 (completion-rate bug)**: Agent found the error but didn't read source code.
   - **Fix**: Updated system prompt to explicitly guide agent to read source code for bug diagnosis.

3. **Question 8 (top-learners bug)**: Agent couldn't find source code files.
   - **Fix**: Updated system prompt to specify backend source code location (`backend/app/`).

4. **Source extraction**: `extract_source` function didn't handle backend source file paths.
   - **Fix**: Added regex patterns for `backend/app/*.py` paths.

5. **Tool message format**: LLM API returned error about tool message format.
   - **Fix**: Added assistant message with `tool_calls` before appending tool results.

### Final Score

**10/10 PASSED**

All local benchmark questions pass:
- ✓ Wiki questions (branch protection, SSH connection)
- ✓ Source code questions (FastAPI framework, router modules)
- ✓ Data queries (item count via `/items/`)
- ✓ API status codes (401 for unauthenticated requests)
- ✓ Bug diagnosis (ZeroDivisionError in completion-rate, TypeError in top-learners)
- ✓ Reasoning questions (request lifecycle, ETL idempotency)

# Task 2 Plan: The Documentation Agent

## Overview

This plan describes how to extend the Task 1 agent with tools and an agentic loop to create a documentation agent that can answer questions by reading the project wiki.

## LLM Provider and Model

- **Provider**: Qwen Code API (self-hosted via `qwen-code-oai-proxy` on VM)
- **Model**: `qwen3-coder-plus`
- **API Type**: OpenAI-compatible chat completions API with function calling support

## Tool Schemas

I will define two tools as function-calling schemas for the LLM:

### 1. `read_file`

```python
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
}
```

### 2. `list_files`

```python
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
```

## Tool Implementation

### Security Measures

Both tools will enforce path security:

1. Resolve the full path and ensure it stays within the project root
2. Reject any path traversal attempts (`../`, absolute paths outside project)
3. Use `Path.resolve()` to get canonical paths and verify they start with project root

### `read_file` Implementation

- Accept relative path from project root
- Validate path security
- Read file contents as UTF-8
- Return contents as string or error message

### `list_files` Implementation

- Accept relative directory path from project root
- Validate path security
- List directory entries (files and subdirectories)
- Return newline-separated listing

## Agentic Loop

The agentic loop will follow this flow:

1. **Initialize**: Create conversation with system prompt + user question
2. **Send to LLM**: Include tool definitions in the API call
3. **Check Response**:
   - If `tool_calls` present → execute tools, append results, repeat
   - If text answer → extract answer and source, return JSON
4. **Limit**: Maximum 10 tool calls per question

### Message Format

```python
messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": question}
]

# Loop:
# 1. Call LLM with messages + tools
# 2. If tool_calls:
#    - Execute each tool
#    - Append tool results as {"role": "tool", ...}
#    - Continue loop
# 3. If text response:
#    - Extract answer
#    - Break loop
```

### System Prompt Strategy

The system prompt will instruct the LLM to:

1. Use `list_files` to discover wiki files when unsure about file locations
2. Use `read_file` to read specific files and find answers
3. Always include a source reference (file path + section anchor) in the final answer
4. Make at most 10 tool calls
5. Return a concise answer with the source

## Output Format

The output JSON will include:

```json
{
    "answer": "The answer text from LLM",
    "source": "wiki/git-workflow.md#resolving-merge-conflicts",
    "tool_calls": [
        {"tool": "list_files", "args": {"path": "wiki"}, "result": "..."},
        {"tool": "read_file", "args": {"path": "wiki/git-workflow.md"}, "result": "..."}
    ]
}
```

## Testing Strategy

I will add 2 regression tests:

1. **Test read_file tool**: Ask "How do you resolve a merge conflict?" and verify:
   - `read_file` appears in `tool_calls`
   - `source` contains `wiki/git-workflow.md`

2. **Test list_files tool**: Ask "What files are in the wiki?" and verify:
   - `list_files` appears in `tool_calls`
   - Agent successfully lists wiki contents

## Implementation Steps

1. Create this plan file
2. Define tool schemas and implementations in `agent.py`
3. Implement the agentic loop with message handling
4. Update system prompt for documentation agent behavior
5. Modify output format to include `source` field
6. Add 2 regression tests
7. Update `AGENT.md` documentation
8. Test manually and run all tests

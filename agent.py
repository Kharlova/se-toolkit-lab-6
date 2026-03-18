#!/usr/bin/env python3
"""
Agent CLI - Calls an LLM and returns a structured JSON answer.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON to stdout: {"answer": "...", "tool_calls": []}
    Debug output goes to stderr.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx


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
    project_root = Path(__file__).parent
    env_path = project_root / ".env.agent.secret"
    
    env_vars = load_env_file(env_path)
    
    config = {
        "api_key": env_vars.get("LLM_API_KEY", ""),
        "api_base": env_vars.get("LLM_API_BASE", ""),
        "model": env_vars.get("LLM_MODEL", "qwen3-coder-plus"),
    }
    
    return config


async def call_llm(config: dict[str, str], question: str) -> str:
    """Call the LLM API and return the response content."""
    url = f"{config['api_base']}/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config['api_key']}",
    }
    
    payload = {
        "model": config["model"],
        "messages": [
            {
                "role": "user",
                "content": question,
            }
        ],
    }
    
    print(f"Calling LLM at {url}...", file=sys.stderr)
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        data = response.json()
        
        if "choices" not in data or len(data["choices"]) == 0:
            raise ValueError("No choices in LLM response")
        
        content = data["choices"][0]["message"]["content"]
        
        usage = data.get("usage", {})
        print(f"Token usage: {usage}", file=sys.stderr)
        
        return content


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
        
        answer = asyncio.run(call_llm(config, question))
        
        result = {
            "answer": answer,
            "tool_calls": [],
        }
        
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

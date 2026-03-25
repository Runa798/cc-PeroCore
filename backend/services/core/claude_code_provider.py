"""Claude Code CLI provider for PeroCore's LLM system.

Spawns the local `claude` CLI as a subprocess and parses its JSON output,
providing OpenAI-compatible non-streaming and streaming interfaces.
"""

import asyncio
import json
import logging
from typing import Any, AsyncIterable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT = 600


def _messages_to_prompt(messages: List[Dict[str, Any]]) -> str:
    """Convert OpenAI-style messages list to a single prompt string."""
    system_parts: List[str] = []
    conv_parts: List[str] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if isinstance(content, list):
            content = "\n".join(
                it.get("text", "") for it in content
                if isinstance(it, dict) and it.get("type") == "text"
            )
        if role == "system":
            system_parts.append(content)
        elif role == "assistant":
            conv_parts.append(f"Assistant: {content}")
        else:
            conv_parts.append(f"Human: {content}")
    parts: List[str] = []
    if system_parts:
        parts.append("[System Context]\n" + "\n\n".join(system_parts))
    if conv_parts:
        parts.append("\n\n".join(conv_parts))
    return "\n\n".join(parts)


def _get_workspace_dir() -> str:
    """Get the clean workspace directory for Claude Code CLI."""
    import os
    workspace = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "claude_workspace")
    if not os.path.exists(workspace):
        os.makedirs(workspace, exist_ok=True)
    return workspace


def _build_args(prompt: str, model: str, streaming: bool) -> List[str]:
    """Build the argument list for the claude CLI invocation."""
    args = ["claude", "-p", prompt, "--cwd", _get_workspace_dir()]
    if streaming:
        args.extend(["--output-format", "stream-json", "--verbose"])
    else:
        args.extend(["--output-format", "json"])
    if model:
        args.extend(["--model", model])
    args.append("--no-session-persistence")
    return args


async def chat_claude_code(
    messages: List[Dict[str, Any]],
    temperature: float = 0.7,
    tools: Optional[List[Dict[str, Any]]] = None,
    model: str = "",
    timeout: float = DEFAULT_TIMEOUT,
) -> Dict[str, Any]:
    """Non-streaming chat via Claude Code CLI. Returns OpenAI-compatible dict."""
    prompt = _messages_to_prompt(messages)
    args = _build_args(prompt, model, streaming=False)
    logger.info("[ClaudeCode] Non-streaming request (model=%s)", model or "default")

    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise TimeoutError(f"[ClaudeCode] Process timed out after {timeout}s")

    if proc.returncode != 0:
        err = stderr.decode(errors="replace").strip()
        logger.error("[ClaudeCode] Process exited with code %d", proc.returncode)
        raise RuntimeError(f"[ClaudeCode] CLI error (exit {proc.returncode}): {err}")

    data = json.loads(stdout.decode(errors="replace").strip())
    result_text = data.get("result", "")
    usage = data.get("usage", {})
    inp, out = usage.get("input_tokens", 0), usage.get("output_tokens", 0)

    return {
        "choices": [{
            "message": {"role": "assistant", "content": result_text},
            "finish_reason": "stop",
        }],
        "usage": {"prompt_tokens": inp, "completion_tokens": out, "total_tokens": inp + out},
    }


async def chat_claude_code_stream(
    messages: List[Dict[str, Any]],
    temperature: float = 0.7,
    tools: Optional[List[Dict[str, Any]]] = None,
    model: str = "",
    timeout: float = DEFAULT_TIMEOUT,
) -> AsyncIterable[Dict[str, Any]]:
    """Streaming chat via Claude Code CLI. Yields delta dicts with 'content' key."""
    prompt = _messages_to_prompt(messages)
    args = _build_args(prompt, model, streaming=True)
    logger.info("[ClaudeCode] Streaming request (model=%s)", model or "default")

    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        assert proc.stdout is not None
        got_assistant = False
        while True:
            try:
                line_bytes = await asyncio.wait_for(proc.stdout.readline(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                raise TimeoutError(f"[ClaudeCode] Stream timed out after {timeout}s")
            if not line_bytes:
                break
            line = line_bytes.decode(errors="replace").strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            event_type = event.get("type", "")
            if event_type in ("system", "rate_limit_event"):
                continue
            if event_type == "assistant":
                # assistant event contains the response text
                for block in event.get("message", {}).get("content", []):
                    if block.get("type") == "text" and block.get("text"):
                        yield {"content": block["text"]}
                        got_assistant = True
            elif event_type == "result":
                # result event also has full text — only yield if we
                # never got an assistant event (fallback)
                if not got_assistant:
                    result_text = event.get("result", "")
                    if result_text:
                        yield {"content": result_text}
                return
    finally:
        if proc.returncode is None:
            proc.kill()
            await proc.wait()
        if proc.returncode and proc.returncode != 0:
            stderr_bytes = await proc.stderr.read() if proc.stderr else b""
            err = stderr_bytes.decode(errors="replace").strip()
            if err:
                logger.error("[ClaudeCode] Stream process exited with code %d", proc.returncode)


def create_claude_code_chat(model: str = "") -> Tuple[Any, Any]:
    """Returns (chat_fn, stream_fn) tuple bound to the given model."""

    async def chat_fn(
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        return await chat_claude_code(messages, temperature, tools, model=model)

    async def stream_fn(
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncIterable[Dict[str, Any]]:
        async for delta in chat_claude_code_stream(messages, temperature, tools, model=model):
            yield delta

    return chat_fn, stream_fn

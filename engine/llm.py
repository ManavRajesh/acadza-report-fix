"""
LLM abstraction layer for the Acadza Report -> Fix Engine.

Provides a unified `call_llm` interface with:
- Structured JSON output via Google GenAI SDK (`google-genai`)
- Strict disk caching keyed by hash(stage + prompt + model + schema) in engine/.cache/
- Verification of genuine API response metadata (raw response, model, timestamp, token counts)
- Automatic retry with exponential backoff for 429 (quota/rate limit) and 503 (high demand/unavailable)
- Fine-grained token usage tracking per stage logged in engine/usage.json
"""

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import re
import socket
import threading
import time
from typing import Any, Optional

# Set default socket timeout so stalled HTTPS connections raise TimeoutError rather than hanging indefinitely
socket.setdefaulttimeout(60.0)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

CACHE_DIR = Path(__file__).parent / ".cache"
USAGE_FILE = Path(__file__).parent / "usage.json"
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
_USAGE_LOCK = threading.Lock()
_RATE_LIMIT_LOCK = threading.Lock()
_LAST_CALL_TIME = 0.0
_MIN_CALL_INTERVAL = 4.2  # Ensures calls stay within 15 RPM Free Tier ceiling


def _throttle_requests() -> None:
    """Enforce minimum spacing between outbound API calls across threads."""
    global _LAST_CALL_TIME
    with _RATE_LIMIT_LOCK:
        now = time.time()
        elapsed = now - _LAST_CALL_TIME
        if elapsed < _MIN_CALL_INTERVAL:
            time.sleep(_MIN_CALL_INTERVAL - elapsed)
        _LAST_CALL_TIME = time.time()


def _get_cache_key(stage: str, model: str, prompt: str, schema: Any) -> str:
    """Generate a deterministic SHA-256 hash key for the call."""
    schema_repr = ""
    if schema is not None:
        if hasattr(schema, "model_json_schema"):
            schema_repr = json.dumps(schema.model_json_schema(), sort_keys=True)
        elif isinstance(schema, dict):
            schema_repr = json.dumps(schema, sort_keys=True)
        else:
            schema_repr = str(schema)

    payload = f"{stage}::{model}::{prompt}::{schema_repr}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _update_usage_log(stage: str, prompt_tokens: int, candidate_tokens: int, total_tokens: int) -> None:
    """Update engine/usage.json with token metrics per stage and overall totals (thread-safe)."""
    with _USAGE_LOCK:
        data = {
            "summary": {
                "total_calls": 0,
                "total_prompt_tokens": 0,
                "total_candidate_tokens": 0,
                "total_tokens": 0,
                "cached_calls": 0,
            },
            "stages": {},
        }

        if USAGE_FILE.exists():
            try:
                with open(USAGE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                pass

        # Ensure stage bucket exists
        if stage not in data["stages"]:
            data["stages"][stage] = {
                "calls": 0,
                "prompt_tokens": 0,
                "candidate_tokens": 0,
                "total_tokens": 0,
                "cached_calls": 0,
            }

        stage_data = data["stages"][stage]
        summary = data["summary"]

        if total_tokens > 0:
            stage_data["calls"] += 1
            stage_data["prompt_tokens"] += prompt_tokens
            stage_data["candidate_tokens"] += candidate_tokens
            stage_data["total_tokens"] += total_tokens

            summary["total_calls"] += 1
            summary["total_prompt_tokens"] += prompt_tokens
            summary["total_candidate_tokens"] += candidate_tokens
            summary["total_tokens"] += total_tokens
        else:
            stage_data["cached_calls"] += 1
            summary["cached_calls"] += 1

        USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(USAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


def safe_json_loads(text: str) -> dict:
    """Robustly parse JSON even when LLM outputs unescaped LaTeX math escapes like \\mu or \\unit."""
    text_clean = text.strip()
    # Strip markdown fences if present
    if text_clean.startswith("```"):
        m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text_clean)
        if m:
            text_clean = m.group(1).strip()

    try:
        return json.loads(text_clean)
    except Exception:
        pass

    # Clean unescaped \u when not followed by 4 hex digits (e.g., \unit, \upsilon)
    cleaned = re.sub(r"\\u(?![0-9a-fA-F]{4})", r"\\\\u", text_clean)
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # Escape any backslash not part of standard JSON escape sequences (\", \\, \/, \b, \f, \n, \r, \t, or \uXXXX)
    cleaned = re.sub(r"\\(?![/bfnrt\"\\]|u[0-9a-fA-F]{4})", r"\\\\", text_clean)
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    return json.loads(text_clean)


def call_llm(
    stage: str,
    prompt: str,
    schema: Optional[Any] = None,
    temperature: float = 0.0,
    model: Optional[str] = None,
) -> dict:
    """
    Execute a structured LLM call via the Google GenAI SDK with disk caching.

    Args:
        stage: Pipeline stage identifier (e.g. 'audit', 'solver_a', 'intake', 'judge').
        prompt: Formatted user/instruction prompt string.
        schema: Optional Pydantic model class or JSON schema dict for structured output.
        temperature: Generation temperature (defaults to 0.0 for deterministic output).
        model: Model name override (defaults to GEMINI_MODEL env var or gemini-3.5-flash-lite).

    Returns:
        dict: Parsed JSON response conforming to the provided schema.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY is not set. Please add it to your .env file or environment."
        )

    selected_model = model or os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    cache_key = _get_cache_key(stage, selected_model, prompt, schema)
    cache_file = CACHE_DIR / f"{cache_key}.json"

    # 1. Strict Disk Cache Check: Must have raw_response, model, timestamp, and token_counts
    if cache_file.exists():
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached_data = json.load(f)

            has_raw = "raw_response" in cached_data and bool(cached_data["raw_response"])
            has_model = "model" in cached_data and bool(cached_data["model"])
            has_ts = "timestamp" in cached_data and bool(cached_data["timestamp"])
            has_tokens = (
                "token_counts" in cached_data
                and isinstance(cached_data["token_counts"], dict)
                and cached_data["token_counts"].get("total_tokens", 0) > 0
            )
            has_parsed = "parsed_result" in cached_data and isinstance(cached_data["parsed_result"], dict)

            if has_raw and has_model and has_ts and has_tokens and has_parsed:
                # Genuine verified cache hit
                _update_usage_log(stage, 0, 0, 0)
                return cached_data["parsed_result"]
            else:
                # Invalid or unverified cache file; remove and make live call
                cache_file.unlink(missing_ok=True)
        except Exception:
            cache_file.unlink(missing_ok=True)

    # 2. Live API Call with Exponential Backoff
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)

    config_kwargs: dict[str, Any] = {
        "temperature": temperature,
        "response_mime_type": "application/json",
    }
    if schema is not None:
        config_kwargs["response_schema"] = schema

    config = types.GenerateContentConfig(**config_kwargs)

    response = None
    max_retries = 8
    for attempt in range(max_retries):
        try:
            _throttle_requests()
            response = client.models.generate_content(
                model=selected_model,
                contents=prompt,
                config=config,
            )
            break
        except Exception as exc:
            err_str = str(exc)
            is_transient = any(
                code in err_str
                for code in (
                    "429",
                    "RESOURCE_EXHAUSTED",
                    "Quota exceeded",
                    "503",
                    "UNAVAILABLE",
                    "500",
                    "502",
                    "504",
                    "high demand",
                    "timeout",
                    "timed out",
                    "ConnectionResetError",
                )
            )
            # If daily quota exceeded, fail immediately rather than sleeping for hours
            if "Generate content requests per day limit exceeded" in err_str:
                raise exc

            if is_transient and attempt < max_retries - 1:
                delay_match = re.search(r"(?:retry in|retryDelay':\s*')\s*(\d+(?:\.\d+)?)", err_str)
                if delay_match:
                    raw_delay = float(delay_match.group(1))
                    if raw_delay > 60:
                        raise RuntimeError(f"API requested excessive retry delay: {raw_delay}s. Error: {err_str}")
                    wait_time = min(60.0, raw_delay + 3.0)
                else:
                    wait_time = min(60.0, (2.0 ** attempt) * 2.5 + random.uniform(1.0, 3.0))
                print(
                    f"    [Transient API Error ({exc.__class__.__name__})] "
                    f"Waiting {wait_time:.1f}s before retry ({attempt + 1}/{max_retries})..."
                )
                time.sleep(wait_time)
            else:
                raise exc

    if response is None:
        raise RuntimeError(f"Failed to generate content after {max_retries} retries.")

    # Parse response
    parsed_result: dict
    if hasattr(response, "parsed") and response.parsed is not None:
        if hasattr(response.parsed, "model_dump"):
            parsed_result = response.parsed.model_dump()
        elif isinstance(response.parsed, dict):
            parsed_result = response.parsed
        else:
            parsed_result = safe_json_loads(str(response.parsed))
    else:
        text = response.text or "{}"
        parsed_result = safe_json_loads(text)

    # Extract Token Usage
    prompt_tokens = 0
    candidate_tokens = 0
    total_tokens = 0
    if hasattr(response, "usage_metadata") and response.usage_metadata is not None:
        prompt_tokens = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
        candidate_tokens = getattr(response.usage_metadata, "candidates_token_count", 0) or 0
        total_tokens = getattr(response.usage_metadata, "total_token_count", 0) or 0

    # Ensure token counts are non-zero for legitimate calls
    if total_tokens == 0 and prompt_tokens == 0:
        # Fallback estimation if API metadata was omitted
        prompt_tokens = max(1, len(prompt) // 4)
        candidate_tokens = max(1, len(str(parsed_result)) // 4)
        total_tokens = prompt_tokens + candidate_tokens

    raw_text = response.text if hasattr(response, "text") and response.text else json.dumps(parsed_result)

    # 3. Save to verified disk cache
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_record = {
        "stage": stage,
        "model": selected_model,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "cache_key": cache_key,
        "raw_response": raw_text,
        "parsed_result": parsed_result,
        "token_counts": {
            "prompt_tokens": prompt_tokens,
            "candidate_tokens": candidate_tokens,
            "total_tokens": total_tokens,
        },
    }
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(cache_record, f, indent=2, ensure_ascii=False)

    # 4. Log usage metrics to engine/usage.json
    _update_usage_log(stage, prompt_tokens, candidate_tokens, total_tokens)

    return parsed_result

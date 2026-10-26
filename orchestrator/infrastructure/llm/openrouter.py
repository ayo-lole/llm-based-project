from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone

from orchestrator.config import CACHE, MODELS, RESULTS, generation_settings

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
PRICES = {
    "openai/gpt-4o": (2.50, 10.00),
    "google/gemini-2.5-flash": (0.30, 2.50),
    "anthropic/claude-sonnet-4": (3.00, 15.00),
}


class OpenRouterClient:
    def __init__(self, model: str, call_log=None, use_cache: bool = True):
        if model not in MODELS:
            raise RuntimeError(f"Unknown model {model!r}; expected one of {MODELS}")
        settings = generation_settings()
        self.model = model
        self.temperature = settings["temperature"]
        self.max_tokens = settings["max_tokens"]
        self.seed = settings["seed"]
        self.prompt_template_version = settings["prompt_template_version"]
        self.gemini_reasoning = settings["gemini_reasoning"]
        self.call_log = call_log
        self.use_cache = use_cache
        self.generation_settings = settings

    def generate(
        self,
        prompt: str,
        system: str | None,
        *,
        run_index: int,
        iteration: int,
        screen_id: str,
        scenario: str,
        preset: str,
    ) -> tuple[str, dict]:
        key = hashlib.sha256(
            json.dumps(
                {
                    "model": self.model,
                    "temp": self.temperature,
                    "sys": system,
                    "p": prompt,
                    "run_index": run_index,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        cache_dir = CACHE / "llm"
        path = cache_dir / f"{key}.txt"
        meta_path = cache_dir / f"{key}.meta.json"
        if self.use_cache and path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
            self._log(key, True, meta, run_index, iteration, screen_id, scenario, preset)
            return path.read_text(encoding="utf-8"), meta
        text, meta = self._call(prompt, system)
        cache_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        meta_path.write_text(json.dumps(meta), encoding="utf-8")
        self._log(key, False, meta, run_index, iteration, screen_id, scenario, preset)
        return text, meta

    def _call(self, prompt: str, system: str | None) -> tuple[str, dict]:
        from openai import OpenAI

        key = os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise RuntimeError("OPENROUTER_API_KEY is required")
        client = OpenAI(api_key=key, base_url=os.getenv("OPENAI_BASE_URL", OPENROUTER_BASE))
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        extra: dict = {"usage": {"include": True}}
        if self.model.startswith("google/gemini-2.5") and self.gemini_reasoning.lower() == "off":
            extra["reasoning"] = {"enabled": False}
        kwargs: dict = {}
        if self.seed is not None:
            kwargs["seed"] = self.seed
        t0 = time.perf_counter()
        resp = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            extra_body=extra,
            **kwargs,
        )
        latency = time.perf_counter() - t0
        usage = getattr(resp, "usage", None)
        tin = getattr(usage, "prompt_tokens", None) if usage else None
        tout = getattr(usage, "completion_tokens", None) if usage else None
        details = getattr(usage, "completion_tokens_details", None) if usage else None
        reasoning = getattr(details, "reasoning_tokens", None) if details else None
        cost = getattr(usage, "cost", None) if usage else None
        if cost is None and tin is not None and self.model in PRICES:
            pin, pout = PRICES[self.model]
            cost = (tin * pin + (tout or 0) * pout) / 1e6
        choice = resp.choices[0]
        returned = getattr(resp, "model", None)
        if returned and returned != self.model and not str(returned).startswith(self.model):
            raise RuntimeError(f"model_returned {returned!r} does not match requested {self.model!r}")
        meta = {
            "model_returned": returned or self.model,
            "finish_reason": getattr(choice, "finish_reason", None),
            "tokens_in": tin,
            "tokens_out": tout,
            "tokens_reasoning": reasoning,
            "cost_usd": cost,
            "latency_s": round(latency, 3),
            "max_tokens": self.max_tokens,
            "seed": self.seed,
            "reasoning": extra.get("reasoning"),
        }
        return choice.message.content or "", meta

    def _log(
        self,
        cache_key: str,
        cached: bool,
        meta: dict,
        run_index: int,
        iteration: int,
        screen_id: str,
        scenario: str,
        preset: str,
    ) -> None:
        rec = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "cache_key": cache_key,
            "cached": cached,
            "model_id": self.model,
            "model_returned": meta.get("model_returned"),
            "run_index": run_index,
            "temperature": self.temperature,
            "max_tokens": meta.get("max_tokens", self.max_tokens),
            "reasoning": meta.get("reasoning"),
            "prompt_template_version": self.prompt_template_version,
            "seed": meta.get("seed"),
            "tokens_in": meta.get("tokens_in"),
            "tokens_out": meta.get("tokens_out"),
            "tokens_reasoning": meta.get("tokens_reasoning"),
            "cost_usd": meta.get("cost_usd"),
            "latency_s": meta.get("latency_s"),
            "finish_reason": meta.get("finish_reason"),
            "screen_id": screen_id,
            "scenario": scenario,
            "preset": preset,
            "iteration": iteration,
        }
        if self.call_log is not None:
            self.call_log.append(rec)
            return
        path = RESULTS / "_calls" / "calls.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")

from orchestrator.infrastructure.llm.openrouter import make_cache_key


def test_cache_key_includes_run_index():
    a = make_cache_key("openai/gpt-4o", 0.2, "sys", "prompt", 1)
    b = make_cache_key("openai/gpt-4o", 0.2, "sys", "prompt", 2)
    c = make_cache_key("openai/gpt-4o", 0.2, "sys", "prompt", 1)
    assert a != b
    assert a == c

import pytest
from traverser_ai_api.config_schema import TraverserDefaults

def test_traverser_defaults_instantiation():
    defaults = TraverserDefaults()
    assert isinstance(defaults, TraverserDefaults)
    # Check default values
    assert defaults.output_dir == "output_data"
    assert defaults.cache_dir == ".cache"
    assert defaults.log_dir == "logs"
    assert defaults.default_model_type == "openai"
    assert defaults.max_tokens == 4000
    assert defaults.temperature == 0.7
    assert defaults.xml_snippet_max_len == 10000
    assert defaults.enable_image_context is True
    assert isinstance(defaults.focus_areas, list)
    assert set(defaults.focus_areas) == {"navigation", "content", "actions"}

def test_traverser_defaults_type_validation():
    # Should raise error for invalid type
    with pytest.raises(ValueError):
        TraverserDefaults(max_tokens=-1)
    with pytest.raises(ValueError):
        TraverserDefaults(temperature=3.0)
    with pytest.raises(ValueError):
        TraverserDefaults(xml_snippet_max_len=0)

def test_traverser_defaults_env_override(monkeypatch):
    monkeypatch.setenv("MAX_TOKENS", "1234")
    defaults = TraverserDefaults()
    assert defaults.max_tokens == 1234

from reliability_lab.config import load_config


def test_default_config_loads() -> None:
    config = load_config("configs/default.yaml")
    assert len(config.providers) >= 2
    assert config.circuit_breaker.failure_threshold > 0
    assert 0 <= config.cache.similarity_threshold <= 1


def test_scenarios_loaded() -> None:
    config = load_config("configs/default.yaml")
    assert len(config.scenarios) >= 2
    names = [s.name for s in config.scenarios]
    assert "primary_timeout_100" in names


def test_all_healthy_scenario_disables_provider_failures() -> None:
    config = load_config("configs/default.yaml")
    scenario = next(s for s in config.scenarios if s.name == "all_healthy")
    assert scenario.provider_overrides == {"primary": 0.0, "backup": 0.0}
    assert scenario.min_availability == 1.0
    assert scenario.max_error_rate == 0.0

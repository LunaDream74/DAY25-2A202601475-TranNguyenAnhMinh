from reliability_lab.chaos import scenario_passed
from reliability_lab.config import ScenarioConfig
from reliability_lab.metrics import RunMetrics


def test_scenario_passes_all_configured_criteria() -> None:
    scenario = ScenarioConfig(
        name="fallback",
        min_availability=0.95,
        min_fallback_success_rate=0.90,
        min_circuit_open_count=1,
        require_recovery=True,
    )
    metrics = RunMetrics(
        total_requests=100,
        successful_requests=98,
        failed_requests=2,
        fallback_successes=19,
        static_fallbacks=1,
        circuit_open_count=1,
        recovery_time_ms=2000,
    )

    assert scenario_passed(scenario, metrics)


def test_scenario_fails_when_any_required_metric_misses() -> None:
    scenario = ScenarioConfig(
        name="healthy",
        min_availability=1.0,
        max_error_rate=0.0,
        max_circuit_open_count=0,
    )
    metrics = RunMetrics(
        total_requests=100,
        successful_requests=99,
        failed_requests=1,
        circuit_open_count=0,
    )

    assert not scenario_passed(scenario, metrics)

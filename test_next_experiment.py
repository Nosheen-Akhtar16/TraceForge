import main


def test_recommends_changed_condition_when_outcomes_differ():
    attempts = [
        {
            "id": "attempt_a",
            "outcome": "reproduced",
            "conditions": {
                "browser": "Chrome",
                "network": "Wi-Fi",
                "logged_in": True,
            },
        },
        {
            "id": "attempt_b",
            "outcome": "not_reproduced",
            "conditions": {
                "browser": "Chrome",
                "network": "Mobile hotspot",
                "logged_in": True,
            },
        },
    ]

    result = main.recommend_next_experiment(attempts)

    assert result["status"] == "recommendation_available"
    assert (
        result["recommended_experiment"]
        ["condition_to_investigate"]
        == "network"
    )
    assert {
        item["condition"] for item in result["keep_constant"]
    } == {"browser", "logged_in"}


def test_returns_insufficient_data_for_one_attempt():
    attempts = [
        {
            "id": "attempt_a",
            "outcome": "reproduced",
            "conditions": {"browser": "Chrome"},
        }
    ]

    result = main.recommend_next_experiment(attempts)

    assert result["status"] == "insufficient_data"
    assert result["recommended_experiment"] is None


def test_ignores_inconclusive_attempts():
    attempts = [
        {
            "id": "attempt_a",
            "outcome": "inconclusive",
            "conditions": {"browser": "Chrome"},
        },
        {
            "id": "attempt_b",
            "outcome": "reproduced",
            "conditions": {"browser": "Chrome"},
        },
    ]

    result = main.recommend_next_experiment(attempts)

    assert result["status"] == "insufficient_data"


def test_requests_more_evidence_for_missing_conditions():
    attempts = [
        {
            "id": "attempt_a",
            "outcome": "reproduced",
            "conditions": {"browser": "Chrome"},
        },
        {
            "id": "attempt_b",
            "outcome": "not_reproduced",
            "conditions": {
                "browser": "Chrome",
                "network": "Wi-Fi",
            },
        },
    ]

    result = main.recommend_next_experiment(attempts)

    assert result["status"] == "more_evidence_needed"
    assert result["recommended_experiment"] is None


def test_requests_unrecorded_variables_when_outcomes_conflict():
    attempts = [
        {
            "id": "attempt_a",
            "outcome": "reproduced",
            "conditions": {"browser": "Chrome"},
        },
        {
            "id": "attempt_b",
            "outcome": "not_reproduced",
            "conditions": {"browser": "Chrome"},
        },
    ]

    result = main.recommend_next_experiment(attempts)

    assert result["status"] == "more_evidence_needed"
    assert "suggested_additional_conditions" in result


def test_requests_more_context_when_conditions_and_outcomes_match():
    attempts = [
        {
            "id": "attempt_a",
            "outcome": "reproduced",
            "conditions": {"browser": "Chrome"},
        },
        {
            "id": "attempt_b",
            "outcome": "reproduced",
            "conditions": {"browser": "Chrome"},
        },
    ]

    result = main.recommend_next_experiment(attempts)

    assert result["status"] == "more_evidence_needed"
    assert result["recommended_experiment"] is None


def test_recommendation_includes_causality_warning():
    attempts = [
        {
            "id": "attempt_a",
            "outcome": "reproduced",
            "conditions": {"network": "Wi-Fi"},
        },
        {
            "id": "attempt_b",
            "outcome": "not_reproduced",
            "conditions": {"network": "Mobile hotspot"},
        },
    ]

    result = main.recommend_next_experiment(attempts)

    assert "causality_warning" in result
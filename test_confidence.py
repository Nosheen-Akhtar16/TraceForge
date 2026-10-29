
import json

from main import calculate_confidence_score


def test_no_attempts_returns_not_assessed():
    result = calculate_confidence_score(
        failure_type="network_error",
        preceding_events=[],
        attempts=[],
        plans=[],
    )

    assert result["confidence_score"] is None
    assert result["confidence_level"] == "not_assessed"


def test_only_inconclusive_attempts_returns_not_assessed():
    attempts = [
        {"outcome": "inconclusive"},
        {"outcome": "inconclusive"},
    ]

    result = calculate_confidence_score(
        failure_type="network_error",
        preceding_events=[],
        attempts=attempts,
        plans=[],
    )

    assert result["confidence_score"] is None
    assert result["confidence_level"] == "not_assessed"
    assert result["attempt_summary"]["inconclusive"] == 2


def test_conflicting_outcomes_are_reported():
    attempts = [
        {"outcome": "reproduced"},
        {"outcome": "not_reproduced"},
    ]

    result = calculate_confidence_score(
        failure_type="network_error",
        preceding_events=[
            {"event_type": "navigation"},
        ],
        attempts=attempts,
        plans=[],
    )

    assert result["confidence_level"] != "high"
    assert any(
        "Conflicting reproduction outcomes" in reason
        for reason in result["confidence_reasons"]
    )
    assert any(
        "Investigate why some attempts" in item
        for item in result["missing_evidence"]
    )


def test_inconclusive_plan_cannot_produce_high_confidence():
    attempts = [
        {"outcome": "reproduced"},
        {"outcome": "reproduced"},
        {"outcome": "inconclusive"},
    ]

    plans = [
        {
            "status": "inconclusive",
            "plan_data": json.dumps({
                "steps": [
                    {
                        "description": "Open the test page",
                        "evidence_status": "available",
                    },
                    {
                        "description": "Verify the failure",
                        "action": "verify_failure",
                    },
                ]
            }),
        }
    ]

    result = calculate_confidence_score(
        failure_type="network_error",
        preceding_events=[
            {"event_type": "navigation"},
        ],
        attempts=attempts,
        plans=plans,
    )

    assert result["confidence_score"] <= 79
    assert result["confidence_level"] == "medium"
    assert result["score_breakdown"]["plan_quality"]["best_plan_status"] == (
        "inconclusive"
    )

def test_plan_attempt_linkage_uses_matching_plan_id():
    attempts = [
        {"id": "attempt-1", "plan_id": "plan-1", "outcome": "inconclusive"},
        {"id": "attempt-2", "plan_id": "plan-1", "outcome": "inconclusive"},
        {"id": "attempt-3", "plan_id": "plan-2", "outcome": "reproduced"},
    ]

    plans = [
        {
            "id": "plan-1",
            "status": "draft",
            "plan_data": json.dumps({
                "steps": [
                    {
                        "description": "Open the test page",
                        "evidence_status": "available",
                    },
                    {
                        "description": "Verify the failure",
                        "action": "verify_failure",
                    },
                ]
            }),
        },
        {
            "id": "plan-2",
            "status": "draft",
            "plan_data": json.dumps({"steps": []}),
        },
    ]

    result = calculate_confidence_score(
        failure_type="network_error",
        preceding_events=[{"event_type": "navigation"}],
        attempts=attempts,
        plans=plans,
    )

    evaluations = result["score_breakdown"]["plan_quality"]["plan_evaluations"]
    plan_1 = next(item for item in evaluations if item["plan_id"] == "plan-1")

    assert plan_1["linked_attempt_count"] == 2
    assert plan_1["linked_inconclusive"] == 2
    assert plan_1["linked_reproduced"] == 0


def test_unlinked_attempts_are_not_attributed_to_a_plan():
    attempts = [
        {"id": "attempt-1", "plan_id": None, "outcome": "reproduced"},
        {"id": "attempt-2", "plan_id": "different-plan", "outcome": "reproduced"},
    ]

    plans = [
        {
            "id": "plan-1",
            "status": "draft",
            "plan_data": json.dumps({
                "steps": [
                    {
                        "description": "Open the test page",
                        "evidence_status": "available",
                    },
                    {
                        "description": "Verify the failure",
                        "action": "verify_failure",
                    },
                ]
            }),
        }
    ]

    result = calculate_confidence_score(
        failure_type="network_error",
        preceding_events=[{"event_type": "navigation"}],
        attempts=attempts,
        plans=plans,
    )

    evaluations = result["score_breakdown"]["plan_quality"]["plan_evaluations"]
    plan_1 = next(item for item in evaluations if item["plan_id"] == "plan-1")

    assert plan_1["linked_attempt_count"] == 0
    assert plan_1["linked_reproduced"] == 0
    assert result["confidence_level"] != "high"

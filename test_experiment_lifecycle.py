import json

import pytest
from fastapi import HTTPException

import main


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test_experiment_lifecycle.db"
    monkeypatch.setattr(main, "DATABASE", str(db_path))

    main.init_db()

    with main.get_connection() as conn:
        conn.execute(
            "INSERT INTO projects (id, name) VALUES (?, ?)",
            ("project-1", "Test Project"),
        )
        conn.execute(
            """
            INSERT INTO sessions (id, project_id, name)
            VALUES (?, ?, ?)
            """,
            ("session-1", "project-1", "Test Session"),
        )
        conn.execute(
            """
            INSERT INTO sessions (id, project_id, name)
            VALUES (?, ?, ?)
            """,
            ("session-2", "project-1", "Other Session"),
        )

    return db_path


def add_failure(session_id="session-1", event_id="failure-1"):
    with main.get_connection() as conn:
        conn.execute("""
            INSERT INTO events (
                id, session_id, event_type, event_data, created_at
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            event_id,
            session_id,
            "network_error",
            json.dumps({"message": "Connection failed"}),
            "2026-01-01T10:00:00",
        ))


def add_attempt(
    attempt_id,
    outcome,
    conditions,
    recommendation_id=None,
):
    with main.get_connection() as conn:
        conn.execute("""
            INSERT INTO reproduction_attempts (
                id,
                session_id,
                failure_event_id,
                outcome,
                notes,
                conditions_json,
                recommendation_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            attempt_id,
            "session-1",
            "failure-1",
            outcome,
            "",
            json.dumps(conditions),
            recommendation_id,
        ))


def test_create_recommendation_persists_record(test_db):
    add_failure()

    add_attempt(
        "attempt-1",
        "reproduced",
        {"browser": "Chrome"},
    )
    add_attempt(
        "attempt-2",
        "not_reproduced",
        {"browser": "Firefox"},
    )

    result = main.create_experiment_recommendation(
        "session-1",
        "failure-1",
    )

    assert result["status"] == "proposed"
    assert result["recommendation_id"].startswith("experiment_")

    with main.get_connection() as conn:
        row = conn.execute("""
            SELECT status, recommendation_data, based_on_attempts
            FROM experiment_recommendations
            WHERE id = ?
        """, (result["recommendation_id"],)).fetchone()

    assert row is not None
    assert row[0] == "proposed"
    assert json.loads(row[1])["status"] == "recommendation_available"
    assert len(json.loads(row[2])) == 2


def test_insufficient_evidence_recommendation_is_still_saved(test_db):
    add_failure()

    result = main.create_experiment_recommendation(
        "session-1",
        "failure-1",
    )

    assert result["recommendation"]["status"] == "insufficient_data"

    history = main.list_experiment_recommendations(
        "session-1",
        "failure-1",
    )

    assert len(history["recommendations"]) == 1


def test_recommendation_status_can_be_updated(test_db):
    add_failure()

    result = main.create_experiment_recommendation(
        "session-1",
        "failure-1",
    )

    recommendation_id = result["recommendation_id"]

    updated = main.update_experiment_recommendation_status(
        "session-1",
        recommendation_id,
        main.ExperimentRecommendationStatusUpdate(
            status="accepted"
        ),
    )

    assert updated["previous_status"] == "proposed"
    assert updated["status"] == "accepted"


def test_attempt_can_link_accepted_recommendation(test_db):
    add_failure()

    add_attempt(
        "attempt-1",
        "reproduced",
        {"browser": "Chrome"},
    )
    add_attempt(
        "attempt-2",
        "not_reproduced",
        {"browser": "Firefox"},
    )

    result = main.create_experiment_recommendation(
        "session-1",
        "failure-1",
    )
    recommendation_id = result["recommendation_id"]

    main.update_experiment_recommendation_status(
        "session-1",
        recommendation_id,
        main.ExperimentRecommendationStatusUpdate(
            status="accepted"
        ),
    )

    attempt = main.create_reproduction_attempt(
        "session-1",
        main.ReproductionAttemptCreate(
            failure_event_id="failure-1",
            recommendation_id=recommendation_id,
            outcome="reproduced",
            conditions={"browser": "Chrome"},
        ),
    )

    assert attempt["recommendation_id"] == recommendation_id

    listed = main.list_reproduction_attempts("session-1")

    linked = [
        item for item in listed["attempts"]
        if item["id"] == attempt["attempt_id"]
    ]

    assert len(linked) == 1
    assert linked[0]["recommendation_id"] == recommendation_id


def test_attempt_cannot_link_proposed_recommendation(test_db):
    add_failure()

    result = main.create_experiment_recommendation(
        "session-1",
        "failure-1",
    )

    with pytest.raises(HTTPException) as exc:
        main.create_reproduction_attempt(
            "session-1",
            main.ReproductionAttemptCreate(
                failure_event_id="failure-1",
                recommendation_id=result["recommendation_id"],
                outcome="reproduced",
            ),
        )

    assert exc.value.status_code == 422


def test_attempt_cannot_link_recommendation_for_another_failure(test_db):
    add_failure()
    add_failure(event_id="failure-2")

    result = main.create_experiment_recommendation(
        "session-1",
        "failure-1",
    )

    main.update_experiment_recommendation_status(
        "session-1",
        result["recommendation_id"],
        main.ExperimentRecommendationStatusUpdate(
            status="accepted"
        ),
    )

    with pytest.raises(HTTPException) as exc:
        main.create_reproduction_attempt(
            "session-1",
            main.ReproductionAttemptCreate(
                failure_event_id="failure-2",
                recommendation_id=result["recommendation_id"],
                outcome="reproduced",
            ),
        )

    assert exc.value.status_code == 422


def test_evaluation_summarizes_linked_attempts(test_db):
    add_failure()

    add_attempt(
        "attempt-1",
        "reproduced",
        {"browser": "Chrome"},
    )
    add_attempt(
        "attempt-2",
        "not_reproduced",
        {"browser": "Firefox"},
    )

    result = main.create_experiment_recommendation(
        "session-1",
        "failure-1",
    )
    recommendation_id = result["recommendation_id"]

    main.update_experiment_recommendation_status(
        "session-1",
        recommendation_id,
        main.ExperimentRecommendationStatusUpdate(
            status="accepted"
        ),
    )

    main.create_reproduction_attempt(
        "session-1",
        main.ReproductionAttemptCreate(
            failure_event_id="failure-1",
            recommendation_id=recommendation_id,
            outcome="reproduced",
            conditions={"browser": "Chrome"},
        ),
    )

    evaluation = main.evaluate_experiment_recommendation(
        "session-1",
        recommendation_id,
    )

    assert evaluation["linked_attempt_count"] == 1
    assert evaluation["outcome_counts"]["reproduced"] == 1
    assert evaluation["recommendation_status"] == "accepted"
    assert "does not establish causation" in evaluation["interpretation"]


def test_recommendation_not_found_for_another_session(test_db):
    add_failure()

    result = main.create_experiment_recommendation(
        "session-1",
        "failure-1",
    )

    with pytest.raises(HTTPException) as exc:
        main.update_experiment_recommendation_status(
            "session-2",
            result["recommendation_id"],
            main.ExperimentRecommendationStatusUpdate(
                status="accepted"
            ),
        )

    assert exc.value.status_code == 404


def test_init_db_migration_is_idempotent(test_db):
    main.init_db()
    main.init_db()

    with main.get_connection() as conn:
        attempt_columns = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(reproduction_attempts)"
            ).fetchall()
        }

        recommendation_table = conn.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'experiment_recommendations'
        """).fetchone()

    assert "recommendation_id" in attempt_columns
    assert recommendation_table is not None
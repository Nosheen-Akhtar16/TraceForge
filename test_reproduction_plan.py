
import json
import sqlite3

import pytest
from fastapi import HTTPException

import main


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """Create an isolated database for each test."""
    db_path = tmp_path / "test_replayos.db"
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


def add_event(
    session_id,
    event_id,
    event_type,
    event_data,
    created_at,
):
    with main.get_connection() as conn:
        conn.execute(
            """
            INSERT INTO events (
                id, session_id, event_type, event_data, created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                event_id,
                session_id,
                event_type,
                json.dumps(event_data),
                created_at,
            ),
        )


def test_generates_and_saves_reproduction_plan(test_db):
    add_event(
        "session-1",
        "nav-1",
        "navigation",
        {"url": "https://example.com"},
        "2026-01-01T10:00:00",
    )
    add_event(
        "session-1",
        "failure-1",
        "network_error",
        {
            "requestUrl": "https://example.com/api",
            "method": "GET",
            "message": "Connection failed",
        },
        "2026-01-01T10:00:05",
    )

    result = main.generate_reproduction_plan(
        "session-1", "failure-1"
    )

    assert result["session_id"] == "session-1"
    assert result["failure_event_id"] == "failure-1"
    assert result["failure_type"] == "network_error"
    assert result["status"] == "draft"
    assert result["step_count"] == len(result["steps"])
    assert result["step_count"] >= 2

    # Confirm the plan was persisted.
    with main.get_connection() as conn:
        saved = conn.execute(
            """
            SELECT session_id, failure_event_id, plan_data, status
            FROM reproduction_plans
            WHERE id = ?
            """,
            (result["plan_id"],),
        ).fetchone()

    assert saved is not None
    assert saved[0] == "session-1"
    assert saved[1] == "failure-1"
    assert json.loads(saved[2])["steps"] == result["steps"]
    assert saved[3] == "draft"


def test_steps_reference_real_source_events(test_db):
    add_event(
        "session-1",
        "nav-1",
        "navigation",
        {"url": "https://example.com"},
        "2026-01-01T10:00:00",
    )
    add_event(
        "session-1",
        "click-1",
        "click",
        {"selector": "#submit"},
        "2026-01-01T10:00:02",
    )
    add_event(
        "session-1",
        "failure-1",
        "network_error",
        {"requestUrl": "https://example.com/api"},
        "2026-01-01T10:00:05",
    )

    result = main.generate_reproduction_plan(
        "session-1", "failure-1"
    )

    with main.get_connection() as conn:
        event_ids = {
            row[0]
            for row in conn.execute(
                "SELECT id FROM events WHERE session_id = ?",
                ("session-1",),
            ).fetchall()
        }

    for step in result["steps"]:
        assert step["source_event_id"] in event_ids

    source_ids = {
        step["source_event_id"] for step in result["steps"]
    }
    assert "nav-1" in source_ids
    assert "click-1" in source_ids
    assert "failure-1" in source_ids


def test_missing_session_returns_404(test_db):
    with pytest.raises(HTTPException) as exc:
        main.generate_reproduction_plan(
            "missing-session", "failure-1"
        )

    assert exc.value.status_code == 404


def test_event_from_another_session_returns_404(test_db):
    add_event(
        "session-2",
        "failure-other",
        "network_error",
        {"message": "Connection failed"},
        "2026-01-01T10:00:05",
    )

    with pytest.raises(HTTPException) as exc:
        main.generate_reproduction_plan(
            "session-1", "failure-other"
        )

    assert exc.value.status_code == 404


def test_non_failure_event_returns_422(test_db):
    add_event(
        "session-1",
        "nav-1",
        "navigation",
        {"url": "https://example.com"},
        "2026-01-01T10:00:00",
    )

    with pytest.raises(HTTPException) as exc:
        main.generate_reproduction_plan("session-1", "nav-1")

    assert exc.value.status_code == 422


def test_missing_context_is_reported(test_db):
    add_event(
        "session-1",
        "failure-1",
        "network_error",
        {},
        "2026-01-01T10:00:05",
    )

    result = main.generate_reproduction_plan(
        "session-1", "failure-1"
    )

    assert result["missing_evidence"]
    assert any(
        step["action"] == "manual_investigation"
        for step in result["steps"]
    )
    assert any(
        step["action"] == "verify_failure"
        for step in result["steps"]
    )
    assert result["limitations"]

def test_next_experiment_rejects_event_from_another_session(test_db):
    add_event(
        "session-2",
        "failure-other",
        "network_error",
        {"message": "Connection failed"},
        "2026-01-01T10:00:05",
    )

    with pytest.raises(HTTPException) as exc:
        main.get_next_experiment_recommendation(
            "session-1",
            "failure-other",
        )

    assert exc.value.status_code == 404


def test_next_experiment_rejects_non_failure_event(test_db):
    add_event(
        "session-1",
        "navigation-1",
        "navigation",
        {"url": "https://example.com"},
        "2026-01-01T10:00:00",
    )

    with pytest.raises(HTTPException) as exc:
        main.get_next_experiment_recommendation(
            "session-1",
            "navigation-1",
        )

    assert exc.value.status_code == 422

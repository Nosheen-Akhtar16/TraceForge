
from contextlib import asynccontextmanager
from uuid import uuid4
from datetime import datetime
import sqlite3
import json
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


DATABASE = "replayos.db"

FAILURE_TYPES = {
    "javascript_error",
    "unhandled_promise_rejection",
    "http_error",
    "network_error",
}

EVIDENCE_WINDOW_SECONDS = 300


def get_connection():
    conn = sqlite3.connect(DATABASE)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'recording',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS reproduction_attempts (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                failure_event_id TEXT NOT NULL,
                outcome TEXT NOT NULL CHECK (
                    outcome IN (
                        'reproduced',
                        'not_reproduced',
                        'inconclusive'
                    )
                ),
                notes TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id),
                FOREIGN KEY (failure_event_id) REFERENCES events(id)
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS reproduction_plans (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                failure_event_id TEXT NOT NULL,
                plan_data TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft'
                    CHECK (
                        status IN (
                            'draft',
                            'passed',
                            'failed',
                            'inconclusive'
                        )
                    ),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id),
                FOREIGN KEY (failure_event_id) REFERENCES events(id)
            )
        """)

        # Safely migrate existing databases.
        columns = conn.execute(
            "PRAGMA table_info(reproduction_attempts)"
        ).fetchall()

        column_names = {column[1] for column in columns}

        if "plan_id" not in column_names:
            conn.execute("""
                ALTER TABLE reproduction_attempts
                ADD COLUMN plan_id TEXT
            """)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="ReplayOS API", lifespan=lifespan)


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class SessionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class EventCreate(BaseModel):
    event_type: str = Field(min_length=1, max_length=50)
    event_data: dict[str, Any] = Field(default_factory=dict)


class ReproductionAttemptCreate(BaseModel):
    failure_event_id: str = Field(min_length=1)
    plan_id: str | None = None
    outcome: Literal[
        "reproduced",
        "not_reproduced",
        "inconclusive",
    ]
    notes: str = Field(default="", max_length=1000)
class ReproductionPlanStatusUpdate(BaseModel):
    status: Literal[
        "draft",
        "passed",
        "failed",
        "inconclusive",
    ]

@app.post("/projects", status_code=201)
def create_project(project: ProjectCreate):
    name = project.name.strip()

    if not name:
        raise HTTPException(422, "Project name cannot be blank")

    project_id = f"proj_{uuid4().hex[:12]}"

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO projects (id, name) VALUES (?, ?)",
            (project_id, name),
        )

    return {
        "project_id": project_id,
        "name": name,
    }


@app.get("/projects")
def list_projects():
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT id, name, created_at
            FROM projects
            ORDER BY created_at DESC, rowid DESC
        """).fetchall()

    return {"projects": [dict(row) for row in rows]}


@app.post("/projects/{project_id}/sessions", status_code=201)
def create_session(project_id: str, session: SessionCreate):
    name = session.name.strip()

    if not name:
        raise HTTPException(422, "Session name cannot be blank")

    session_id = f"sess_{uuid4().hex[:12]}"

    with get_connection() as conn:
        project = conn.execute(
            "SELECT id FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()

        if project is None:
            raise HTTPException(404, "Project not found")

        conn.execute("""
            INSERT INTO sessions (id, project_id, name)
            VALUES (?, ?, ?)
        """, (session_id, project_id, name))

    return {
        "session_id": session_id,
        "project_id": project_id,
        "name": name,
        "status": "recording",
    }


@app.get("/projects/{project_id}/sessions")
def list_sessions(project_id: str):
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row

        project = conn.execute(
            "SELECT id FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()

        if project is None:
            raise HTTPException(404, "Project not found")

        rows = conn.execute("""
            SELECT id, project_id, name, status, created_at
            FROM sessions
            WHERE project_id = ?
            ORDER BY created_at DESC, rowid DESC
        """, (project_id,)).fetchall()

    return {"sessions": [dict(row) for row in rows]}


@app.post("/sessions/{session_id}/events", status_code=201)
def create_event(session_id: str, event: EventCreate):
    event_type = event.event_type.strip()

    if not event_type:
        raise HTTPException(422, "Event type cannot be blank")

    event_id = f"evt_{uuid4().hex[:12]}"

    with get_connection() as conn:
        session = conn.execute(
            "SELECT id FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()

        if session is None:
            raise HTTPException(404, "Session not found")

        conn.execute("""
            INSERT INTO events (id, session_id, event_type, event_data)
            VALUES (?, ?, ?, ?)
        """, (
            event_id,
            session_id,
            event_type,
            json.dumps(event.event_data),
        ))

    return {
        "event_id": event_id,
        "session_id": session_id,
        "event_type": event_type,
        "event_data": event.event_data,
    }


@app.get("/sessions/{session_id}/events")
def list_events(session_id: str):
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row

        session = conn.execute(
            "SELECT id FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()

        if session is None:
            raise HTTPException(404, "Session not found")

        rows = conn.execute("""
            SELECT id, session_id, event_type, event_data, created_at
            FROM events
            WHERE session_id = ?
            ORDER BY created_at ASC, rowid ASC
        """, (session_id,)).fetchall()

    events = []

    for row in rows:
        item = dict(row)
        item["event_data"] = json.loads(item["event_data"])
        events.append(item)

    return {"events": events}

@app.get("/sessions/{session_id}/evidence")
def get_session_evidence(session_id: str):
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row

        session = conn.execute(
            "SELECT id FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()

        if session is None:
            raise HTTPException(404, "Session not found")

        event_rows = conn.execute("""
            SELECT id, session_id, event_type, event_data, created_at
            FROM events
            WHERE session_id = ?
            ORDER BY created_at ASC, rowid ASC
        """, (session_id,)).fetchall()

        attempt_rows = conn.execute("""
    SELECT
        id,
        failure_event_id,
        plan_id,
        outcome,
        notes,
        created_at
    FROM reproduction_attempts
    WHERE session_id = ?
    ORDER BY created_at ASC, rowid ASC
""", (session_id,)).fetchall()

        plan_rows = conn.execute("""
            SELECT id, failure_event_id, plan_data, status, created_at
            FROM reproduction_plans
            WHERE session_id = ?
            ORDER BY created_at ASC, rowid ASC
        """, (session_id,)).fetchall()

    # Convert event rows into dictionaries.
    events = []

    for row in event_rows:
        item = dict(row)
        item["event_data"] = json.loads(item["event_data"])
        events.append(item)

    # Group reproduction attempts by failure event.
    attempts_by_failure = {}

    for row in attempt_rows:
        attempt = dict(row)
        failure_id = attempt["failure_event_id"]

        attempts_by_failure.setdefault(
    failure_id, []
).append({
    "id": attempt["id"],
    "plan_id": attempt["plan_id"],
    "outcome": attempt["outcome"],
    "notes": attempt["notes"],
    "created_at": attempt["created_at"],
})

    # Group saved reproduction plans by failure event.
    plans_by_failure = {}

    for row in plan_rows:
        plan = dict(row)
        plan_data = json.loads(plan["plan_data"])

        # The database status is the authoritative status.
        plan_data["plan_status"] = plan["status"]

        saved_plan = {
            "plan_id": plan["id"],
            "status": plan["status"],
            "created_at": plan["created_at"],
            "plan_data": plan_data,
        }

        plans_by_failure.setdefault(
            plan["failure_event_id"], []
        ).append(saved_plan)

    failures = []

    for index, event in enumerate(events):
        if event["event_type"] not in FAILURE_TYPES:
            continue

        failure_time = datetime.fromisoformat(
            event["created_at"]
        )

        preceding_events = []

        for earlier_event in events[:index]:
            earlier_time = datetime.fromisoformat(
                earlier_event["created_at"]
            )

            age_seconds = (
                failure_time - earlier_time
            ).total_seconds()

            if 0 <= age_seconds <= EVIDENCE_WINDOW_SECONDS:
                preceding_events.append(earlier_event)

        attempts = attempts_by_failure.get(
            event["id"], []
        )

        plans = plans_by_failure.get(
            event["id"], []
        )

        event_types = {
            item["event_type"]
            for item in preceding_events
        }

        # Count manually recorded reproduction outcomes.
        reproduced_count = sum(
            attempt["outcome"] == "reproduced"
            for attempt in attempts
        )

        not_reproduced_count = sum(
            attempt["outcome"] == "not_reproduced"
            for attempt in attempts
        )

        inconclusive_count = sum(
            attempt["outcome"] == "inconclusive"
            for attempt in attempts
        )

        # Plans are ordered oldest to newest.
        latest_plan = plans[-1] if plans else None

        failures.append({
            "failure_event": event,

            "preceding_events": preceding_events,

            "evidence_summary": {
                "preceding_event_count": len(
                    preceding_events
                ),
                "has_click_evidence": (
                    "click" in event_types
                ),
                "has_navigation_evidence": (
                    "navigation" in event_types
                ),
                "has_network_failure_evidence": bool(
                    event_types
                    & {"http_error", "network_error"}
                ),
            },

            "reproduction": {
                "attempt_count": len(attempts),
                "reproduced_count": reproduced_count,
                "not_reproduced_count": (
                    not_reproduced_count
                ),
                "inconclusive_count": inconclusive_count,
                "last_attempt": (
                    attempts[-1] if attempts else None
                ),
                "attempts": attempts,
            },

            "reproduction_plans": {
                "plan_count": len(plans),
                "latest_plan": latest_plan,
                "plans": plans,
            },

            "limitations": [
                "Temporal proximity does not prove causation.",
                "Missing events may mean the interaction was not captured.",
                "Reproduction outcomes are manually recorded.",
                "Reproduction plan steps are not executed automatically.",
                "A recorded reproduction outcome does not establish the root cause.",
            ],
        })

    # Count all event types in the session.
    event_counts = {}

    for event in events:
        event_type = event["event_type"]

        event_counts[event_type] = (
            event_counts.get(event_type, 0) + 1
        )

    return {
        "session_id": session_id,
        "total_events": len(events),
        "event_counts": event_counts,
        "failure_count": len(failures),
        "failures": failures,
    }



@app.get(
    "/sessions/{session_id}/failures/{failure_event_id}/reproduction-plan"
)
def generate_reproduction_plan(
    session_id: str,
    failure_event_id: str,
):
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row

        session = conn.execute(
            "SELECT id FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()

        if session is None:
            raise HTTPException(404, "Session not found")

        rows = conn.execute("""
            SELECT id, session_id, event_type, event_data, created_at
            FROM events
            WHERE session_id = ?
            ORDER BY created_at ASC, rowid ASC
        """, (session_id,)).fetchall()

    events = []

    for row in rows:
        event = dict(row)

        try:
            event["event_data"] = json.loads(event["event_data"])
        except (json.JSONDecodeError, TypeError):
            event["event_data"] = {}

        events.append(event)

    failure_index = next(
        (
            index
            for index, event in enumerate(events)
            if event["id"] == failure_event_id
        ),
        None,
    )

    if failure_index is None:
        raise HTTPException(
            404,
            "Failure event not found in this session",
        )

    failure = events[failure_index]

    if failure["event_type"] not in FAILURE_TYPES:
        raise HTTPException(
            422,
            "The selected event is not a recognized failure event",
        )

    failure_details = failure["event_data"]

    failure_time = datetime.fromisoformat(
        failure["created_at"]
    )

    preceding_events = []

    for event in events[:failure_index]:
        try:
            event_time = datetime.fromisoformat(
                event["created_at"]
            )
        except (ValueError, TypeError):
            continue

        age_seconds = (
            failure_time - event_time
        ).total_seconds()

        if 0 <= age_seconds <= EVIDENCE_WINDOW_SECONDS:
            preceding_events.append(event)

    steps = []
    navigation_count = 0
    click_count = 0
    missing_evidence = []

    request_url = (
        failure_details.get("requestUrl")
        or failure_details.get("request_url")
    )

    request_method = (
        failure_details.get("method")
        or failure_details.get("requestMethod")
        or failure_details.get("request_method")
    )

    error_message = (
        failure_details.get("message")
        or failure_details.get("error")
        or failure_details.get("statusText")
    )

    failure_status = failure_details.get("status")

    failure_page_url = (
        failure_details.get("url")
        or failure_details.get("pageUrl")
    )

    for event in preceding_events:
        data = event["event_data"]
        event_type = event["event_type"]

        if event_type == "navigation":
            navigation_count += 1
            url = data.get("url")

            if url:
                description = (
                    f"Open the recorded page: {url}"
                )
                evidence_status = "recorded_url"
            else:
                description = (
                    "Review the recorded navigation event. "
                    "The page URL was not captured."
                )
                evidence_status = "url_missing"
                missing_evidence.append(
                    "A preceding navigation event has no recorded URL."
                )

            action = "navigation"

        elif event_type == "click":
            click_count += 1

            target = (
                data.get("selector")
                or data.get("target")
                or data.get("text")
            )

            if target:
                description = (
                    "Manually inspect and repeat the recorded click "
                    f"on: {target}. Confirm that this is the same "
                    "element as in the original interaction."
                )
                evidence_status = "recorded_target"
            else:
                description = (
                    "Inspect the recorded click and identify the "
                    "target element before repeating the interaction. "
                    "The click target details are incomplete."
                )
                evidence_status = "target_details_missing"

                missing_evidence.append(
                    "A preceding click event has incomplete target details."
                )

            action = "click"

        else:
            continue

        steps.append({
            "step": len(steps) + 1,
            "action": action,
            "description": description,
            "source_event_id": event["id"],
            "source_event_time": event["created_at"],
            "evidence_status": evidence_status,
        })

    if not steps:
        steps.append({
            "step": 1,
            "action": "manual_investigation",
            "description": (
                "No preceding navigation or click events were found "
                "within the evidence time window. Inspect the recorded "
                "failure details and gather the missing interaction "
                "evidence before attempting reproduction."
            ),
            "source_event_id": failure_event_id,
            "evidence_status": "insufficient_context",
        })

        missing_evidence.append(
            "No preceding navigation or click steps were available "
            "within the evidence time window."
        )

    verification_parts = [
        "Manually repeat the interaction that originally triggered "
        "the failure.",
        "Open the browser DevTools Network tab and inspect the "
        "corresponding request, if one was made.",
    ]

    if failure_page_url:
        verification_parts.append(
            f"The recorded page URL is {failure_page_url}. "
            "Confirm that the reproduction is performed in the "
            "relevant page context."
        )

    if request_method and request_url:
        verification_parts.append(
            "Compare the request method and URL with the captured "
            f"request: {request_method} {request_url}."
        )
    else:
        verification_parts.append(
            "The original request method or URL is incomplete. "
            "Identify the corresponding request in DevTools."
        )

    if failure_status is not None:
        verification_parts.append(
            f"The recorded HTTP status is {failure_status}. "
            "Compare it with the status observed during reproduction."
        )
    else:
        verification_parts.append(
            "The HTTP status was not captured. Record the observed "
            "status if available; do not assume a specific status."
        )

    if error_message:
        verification_parts.append(
            f"The recorded error detail is: {error_message}. "
            "Compare it with the new observation."
        )

    verification_parts.append(
        "Record whether the failure reproduced, did not reproduce, "
        "or could not be determined. A matching error message alone "
        "does not establish the root cause."
    )

    steps.append({
        "step": len(steps) + 1,
        "action": "verify_failure",
        "description": " ".join(verification_parts),
        "source_event_id": failure_event_id,
        "evidence_status": "manual_verification_required",
    })

    if not request_url:
        missing_evidence.append(
            "The failed request URL was not captured."
        )

    if not request_method:
        missing_evidence.append(
            "The failed request method was not captured."
        )

    if failure_status is None:
        missing_evidence.append(
            "The HTTP status is unavailable. The exact failure cause "
            "cannot be established from the captured status."
        )

    if not error_message:
        missing_evidence.append(
            "No usable error message or status text was captured."
        )

    if failure["event_type"] in {
        "network_error",
        "http_error",
    } and not request_url:
        missing_evidence.append(
            "Without the failed request URL, the specific request "
            "cannot be reliably identified."
        )

    limitations = [
        "Recorded events provide context but do not prove the cause "
        "of the failure.",
        "Generated steps are suggestions and are not executed "
        "automatically.",
        "The generated plan has not been automatically validated.",
        "The final reproduction outcome must be recorded manually.",
    ]

    if navigation_count == 0:
        limitations.append(
            "No preceding navigation event was captured."
        )

    if click_count == 0:
        limitations.append(
            "No preceding click event was captured."
        )

    if failure_status is None:
        limitations.append(
            "The captured failure does not include an HTTP status. "
            "A network failure may occur without an HTTP response."
        )

    plan_id = f"plan_{uuid4().hex[:12]}"

    plan_data = {
        "session_id": session_id,
        "failure_event_id": failure_event_id,
        "failure_type": failure["event_type"],
        "failure_details": failure_details,
        "step_count": len(steps),
        "steps": steps,
        "evidence_summary": {
            "preceding_event_count": len(preceding_events),
            "navigation_event_count": navigation_count,
            "click_event_count": click_count,
        },
        "missing_evidence": list(dict.fromkeys(missing_evidence)),
        "limitations": limitations,
    }

    with get_connection() as conn:
        conn.execute("""
            INSERT INTO reproduction_plans (
                id,
                session_id,
                failure_event_id,
                plan_data,
                status
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            plan_id,
            session_id,
            failure_event_id,
            json.dumps(plan_data),
            "draft",
        ))

    return {
        "plan_id": plan_id,
        **plan_data,
        "status": "draft",
    }



@app.get("/sessions/{session_id}/reproduction-plans")
def list_reproduction_plans(session_id: str):
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row

        session = conn.execute(
            "SELECT id FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()

        if session is None:
            raise HTTPException(404, "Session not found")

        rows = conn.execute("""
            SELECT
                id,
                session_id,
                failure_event_id,
                plan_data,
                status,
                created_at
            FROM reproduction_plans
            WHERE session_id = ?
            ORDER BY created_at ASC, rowid ASC
        """, (session_id,)).fetchall()

    plans = []

    for row in rows:
        plan = dict(row)
        plan["plan_data"] = json.loads(plan["plan_data"])
        plans.append(plan)

    return {
        "session_id": session_id,
        "plan_count": len(plans),
        "plans": plans,
    }


@app.patch(
    "/sessions/{session_id}/reproduction-plans/{plan_id}/status"
)
def update_reproduction_plan_status(
    session_id: str,
    plan_id: str,
    update: ReproductionPlanStatusUpdate,
):
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row

        plan = conn.execute("""
            SELECT id, status, plan_data
            FROM reproduction_plans
            WHERE id = ? AND session_id = ?
        """, (plan_id, session_id)).fetchone()

        if plan is None:
            raise HTTPException(
                404,
                "Reproduction plan not found",
            )

        previous_status = plan["status"]

        plan_data = json.loads(plan["plan_data"])
        plan_data["plan_status"] = update.status

        conn.execute("""
            UPDATE reproduction_plans
            SET status = ?, plan_data = ?
            WHERE id = ? AND session_id = ?
        """, (
            update.status,
            json.dumps(plan_data),
            plan_id,
            session_id,
        ))

        # Read the updated record back from SQLite.
        updated_plan = conn.execute("""
            SELECT status, plan_data
            FROM reproduction_plans
            WHERE id = ? AND session_id = ?
        """, (plan_id, session_id)).fetchone()

    return {
        "plan_id": plan_id,
        "session_id": session_id,
        "previous_status": previous_status,
        "status": updated_plan["status"],
        "plan_status": json.loads(
            updated_plan["plan_data"]
        ).get("plan_status"),
    }


@app.post(
    "/sessions/{session_id}/reproduction-attempts",
    status_code=201,
)
def create_reproduction_attempt(
    session_id: str,
    attempt: ReproductionAttemptCreate,
):
    attempt_id = f"attempt_{uuid4().hex[:12]}"
    notes = attempt.notes.strip()

    with get_connection() as conn:
        session = conn.execute(
            "SELECT id FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()

        if session is None:
            raise HTTPException(404, "Session not found")

        failure = conn.execute("""
            SELECT id, event_type
            FROM events
            WHERE id = ? AND session_id = ?
        """, (
            attempt.failure_event_id,
            session_id,
        )).fetchone()

        if failure is None:
            raise HTTPException(
                404,
                "Failure event not found in this session",
            )

        if failure[1] not in FAILURE_TYPES:
            raise HTTPException(
                422,
                "The selected event is not a recognized failure event",
            )

        # Validate the reproduction plan when plan_id is provided.
        if attempt.plan_id is not None:
            plan = conn.execute("""
                SELECT id, failure_event_id
                FROM reproduction_plans
                WHERE id = ? AND session_id = ?
            """, (
                attempt.plan_id,
                session_id,
            )).fetchone()

            if plan is None:
                raise HTTPException(
                    404,
                    "Reproduction plan not found in this session",
                )

            if plan[1] != attempt.failure_event_id:
                raise HTTPException(
                    422,
                    "The reproduction plan belongs to a different failure",
                )

        conn.execute("""
            INSERT INTO reproduction_attempts (
                id,
                session_id,
                failure_event_id,
                outcome,
                notes,
                plan_id
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            attempt_id,
            session_id,
            attempt.failure_event_id,
            attempt.outcome,
            notes,
            attempt.plan_id,
        ))

    return {
        "attempt_id": attempt_id,
        "session_id": session_id,
        "failure_event_id": attempt.failure_event_id,
        "plan_id": attempt.plan_id,
        "outcome": attempt.outcome,
        "notes": notes,
    }


@app.get("/sessions/{session_id}/reproduction-attempts")
def list_reproduction_attempts(session_id: str):
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row

        session = conn.execute(
            "SELECT id FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()

        if session is None:
            raise HTTPException(404, "Session not found")

        rows = conn.execute("""
            SELECT
                id,
                session_id,
                failure_event_id,
                plan_id,
                outcome,
                notes,
                created_at
            FROM reproduction_attempts
            WHERE session_id = ?
            ORDER BY created_at ASC, rowid ASC
        """, (session_id,)).fetchall()

    return {
        "attempts": [dict(row) for row in rows]
    }
def calculate_confidence_score(
    failure_type,
    preceding_events,
    attempts,
    plans,
):
    informative_attempts = [
        attempt
        for attempt in attempts
        if attempt["outcome"] in {"reproduced", "not_reproduced"}
    ]

    reproduced_count = sum(
        attempt["outcome"] == "reproduced"
        for attempt in informative_attempts
    )

    not_reproduced_count = sum(
        attempt["outcome"] == "not_reproduced"
        for attempt in informative_attempts
    )

    inconclusive_count = sum(
        attempt["outcome"] == "inconclusive"
        for attempt in attempts
    )

    attempt_summary = {
        "total": len(attempts),
        "reproduced": reproduced_count,
        "not_reproduced": not_reproduced_count,
        "inconclusive": inconclusive_count,
    }

    if not informative_attempts:
        return {
            "confidence_score": None,
            "confidence_level": "not_assessed",
            "score_type": "heuristic_evidence_score_not_probability",
            "message": (
                "No informative reproduction outcomes are available yet."
            ),
            "score_breakdown": {
                "repeatability": {
                    "score": None,
                    "max_score": 40,
                },
                "context_evidence": {
                    "score": None,
                    "max_score": 20,
                },
                "plan_quality": {
                    "score": None,
                    "max_score": 20,
                },
                "outcome_consistency": {
                    "score": None,
                    "max_score": 20,
                },
            },
            "attempt_summary": attempt_summary,
            "missing_evidence": [
                "Record an informative reproduction outcome."
            ],
            "confidence_reasons": [
                "Confidence cannot be assessed without informative attempts."
            ],
        }

    total_informative = len(informative_attempts)

    repeatability_score = round(
        40 * reproduced_count / total_informative
    )

    event_types = {
        event["event_type"]
        for event in preceding_events
    }

    context_signals = []

    if "navigation" in event_types:
        context_signals.append("Recorded navigation context")

    if "click" in event_types:
        context_signals.append("Recorded click context")

    if failure_type in {"network_error", "http_error"}:
        if "network_error" in event_types or "http_error" in event_types:
            context_signals.append(
                "Additional network-related failure event"
            )

    context_score = min(20, len(context_signals) * 5)

    best_plan_score = 0
    best_plan_status = None
    plan_quality_notes = []
    plan_evaluations = []

    status_multipliers = {
        "passed": 1.0,
        "draft": 0.75,
        "inconclusive": 0.5,
        "failed": 0.4,
    }

    for plan in plans:
        try:
            plan_data = json.loads(plan["plan_data"])
        except (TypeError, json.JSONDecodeError):
            plan_data = {}

        if not isinstance(plan_data, dict):
            plan_data = {}

        steps = plan_data.get("steps", [])

        if not isinstance(steps, list):
            steps = []

        usable_steps = [
            step
            for step in steps
            if isinstance(step, dict)
            and isinstance(step.get("description"), str)
            and step["description"].strip()
            and step.get("evidence_status") not in {
                "insufficient_context",
                "url_missing",
                "target_details_missing",
            }
        ]

        has_verification = any(
            isinstance(step, dict)
            and step.get("action") == "verify_failure"
            for step in steps
        )

        structural_score = 0

        if usable_steps:
            structural_score += 10

        if has_verification:
            structural_score += 10

        plan_id = plan.get("id", plan.get("plan_id"))

        linked_attempts = [
    attempt
    for attempt in attempts
    if (
        attempt.get("plan_id") is not None
        and str(attempt.get("plan_id")) == str(plan_id)
    )
]

        linked_reproduced = sum(
            attempt["outcome"] == "reproduced"
            for attempt in linked_attempts
        )

        linked_not_reproduced = sum(
            attempt["outcome"] == "not_reproduced"
            for attempt in linked_attempts
        )

        linked_inconclusive = sum(
            attempt["outcome"] == "inconclusive"
            for attempt in linked_attempts
        )

        status = plan["status"]
        multiplier = status_multipliers.get(status, 0.4)

        if status == "passed" and linked_reproduced == 0:
            multiplier = status_multipliers["draft"]

        adjusted_score = round(structural_score * multiplier)

        plan_evaluations.append({
            "plan_id": plan_id,
            "status": status,
            "linked_attempt_count": len(linked_attempts),
            "linked_reproduced": linked_reproduced,
            "linked_not_reproduced": linked_not_reproduced,
            "linked_inconclusive": linked_inconclusive,
            "structural_score": structural_score,
            "adjusted_score": adjusted_score,
        })

        if adjusted_score > best_plan_score:
            best_plan_score = adjusted_score
            best_plan_status = status

    if not plans:
        plan_quality_notes.append(
            "No reproduction plan has been saved for this failure."
        )
    else:
        plan_quality_notes.append(
            "Plan quality considers actionable steps, verification, "
            "recorded status, and linked reproduction attempts."
        )
        plan_quality_notes.append(
            "A passed status without a linked reproduced attempt "
            "does not receive the full passed-status multiplier."
        )
        plan_quality_notes.append(
            "Linked attempts are manually recorded and do not "
            "independently establish the root cause."
        )

    outcome_consistency_score = round(
        20
        * max(reproduced_count, not_reproduced_count)
        / total_informative
    )

    raw_score = (
        repeatability_score
        + context_score
        + best_plan_score
        + outcome_consistency_score
    )

    confidence_reasons = []

    has_passed_plan = any(
        evaluation["status"] == "passed"
        and evaluation["linked_reproduced"] >= 1
        for evaluation in plan_evaluations
    )

    has_useful_context = bool(context_signals)

    if reproduced_count >= 2:
        confidence_reasons.append(
            "The failure has been reproduced in at least two attempts."
        )
    else:
        confidence_reasons.append(
            "Fewer than two informative attempts reproduced the failure."
        )

    if has_useful_context:
        confidence_reasons.append(
            "Recorded events provide some context for investigating the failure."
        )
    else:
        confidence_reasons.append(
            "No selected navigation or interaction context was recorded."
        )

    if has_passed_plan:
        confidence_reasons.append(
            "At least one reproduction plan has a manually recorded passed status."
        )
    else:
        confidence_reasons.append(
            "No reproduction plan has a passed status."
        )

    if reproduced_count and not_reproduced_count:
        confidence_reasons.append(
            "Conflicting reproduction outcomes require further investigation."
        )

    if inconclusive_count:
        confidence_reasons.append(
            "Some attempts are inconclusive and need review."
        )

    if reproduced_count >= 2 and has_passed_plan and has_useful_context:
        total_score = raw_score
    else:
        total_score = min(raw_score, 79)

    if (
        total_score >= 80
        and reproduced_count >= 2
        and has_passed_plan
        and has_useful_context
        and not (reproduced_count and not_reproduced_count)
    ):
        confidence_level = "high"
    elif total_score >= 50:
        confidence_level = "medium"
    else:
        confidence_level = "low"

    missing_evidence = []

    if reproduced_count < 2:
        missing_evidence.append(
            "Reproduce the same failure in at least two attempts."
        )

    if not has_useful_context:
        missing_evidence.append(
            "Capture relevant navigation or interaction context."
        )

    if not plans:
        missing_evidence.append(
            "Create and save a reproduction plan."
        )
    elif not has_passed_plan:
        missing_evidence.append(
            "Validate a reproduction plan and update its status "
            "when the evidence supports doing so."
        )

    if best_plan_score < 15:
        missing_evidence.append(
            "Improve the plan with actionable steps and explicit "
            "failure verification."
        )

    if reproduced_count and not_reproduced_count:
        missing_evidence.append(
            "Investigate why some attempts reproduce the failure "
            "while others do not."
        )

    if inconclusive_count:
        missing_evidence.append(
            "Review inconclusive attempts and record a clearer outcome "
            "when sufficient evidence is available."
        )

    return {
        "confidence_score": total_score,
        "confidence_level": confidence_level,
        "score_type": "heuristic_evidence_score_not_probability",
        "raw_component_score": raw_score,
        "score_breakdown": {
            "repeatability": {
                "score": repeatability_score,
                "max_score": 40,
                "explanation": (
                    f"{reproduced_count} reproduced out of "
                    f"{total_informative} informative attempts."
                ),
            },
            "context_evidence": {
                "score": context_score,
                "max_score": 20,
                "signals": context_signals,
                "explanation": (
                    "Scores selected recorded context signals. "
                    "Repeated or related events do not prove causation."
                ),
            },
            "plan_quality": {
                "score": best_plan_score,
                "max_score": 20,
                "plan_evaluations": plan_evaluations,
                "plans_evaluated": len(plans),
                "best_plan_status": best_plan_status,
                "explanation": (
                    "The best structural plan score is adjusted using "
                    "the plan's manually recorded status."
                ),
            },
            "outcome_consistency": {
                "score": outcome_consistency_score,
                "max_score": 20,
                "explanation": (
                    "Measures agreement among informative outcomes. "
                    "Inconclusive attempts are excluded."
                ),
            },
        },
        "attempt_summary": attempt_summary,
        "missing_evidence": missing_evidence,
        "confidence_reasons": confidence_reasons,
        "plan_quality_notes": plan_quality_notes,
        "limitations": [
            "This heuristic has not been statistically calibrated.",
            "The score is not a probability that the root cause is correct.",
            "Recorded context does not establish the root cause.",
            "Reproduction outcomes and plan statuses are manually recorded.",
            "Repeated failures may share the same underlying cause or conditions.",
        ],
    }


@app.get(
    "/sessions/{session_id}/failures/{failure_event_id}/confidence"
)
def get_failure_confidence(
    session_id: str,
    failure_event_id: str,
):
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row

        session = conn.execute(
            "SELECT id FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()

        if session is None:
            raise HTTPException(404, "Session not found")

        failure_row = conn.execute(
            """
            SELECT id, event_type, event_data, created_at
            FROM events
            WHERE id = ? AND session_id = ?
            """,
            (failure_event_id, session_id),
        ).fetchone()

        if failure_row is None:
            raise HTTPException(
                404,
                "Failure event not found in this session",
            )

        failure = dict(failure_row)

        if failure["event_type"] not in FAILURE_TYPES:
            raise HTTPException(
                422,
                "The selected event is not a recognized failure event",
            )

        event_rows = conn.execute(
            """
            SELECT id, event_type, event_data, created_at
            FROM events
            WHERE session_id = ?
            ORDER BY created_at ASC, rowid ASC
            """,
            (session_id,),
        ).fetchall()

        attempt_rows = conn.execute(
            """
            
            SELECT id, plan_id, outcome, notes, created_at
            FROM reproduction_attempts
            WHERE session_id = ? AND failure_event_id = ?
            ORDER BY created_at ASC, rowid ASC
            """,
            (session_id, failure_event_id),
        ).fetchall()

        plan_rows = conn.execute(
            """
            SELECT id, plan_data, status, created_at
            FROM reproduction_plans
            WHERE session_id = ? AND failure_event_id = ?
            ORDER BY created_at DESC, rowid DESC
            """,
            (session_id, failure_event_id),
        ).fetchall()

    failure_time = datetime.fromisoformat(failure["created_at"])
    preceding_events = []

    for row in event_rows:
        event = dict(row)

        if event["id"] == failure_event_id:
            break

        event_time = datetime.fromisoformat(event["created_at"])
        age_seconds = (failure_time - event_time).total_seconds()

        if 0 <= age_seconds <= EVIDENCE_WINDOW_SECONDS:
            event["event_data"] = json.loads(event["event_data"])
            preceding_events.append(event)

    attempts = [dict(row) for row in attempt_rows]
    plans = [dict(row) for row in plan_rows]

    result = calculate_confidence_score(
        failure_type=failure["event_type"],
        preceding_events=preceding_events,
        attempts=attempts,
        plans=plans,
    )

    return {
        "session_id": session_id,
        "failure_event_id": failure_event_id,
        "failure_type": failure["event_type"],
        "failure_details": json.loads(failure["event_data"]),
        "confidence": result,
    }

# TraceForge
### Evidence-driven browser failure investigation

TraceForge organizes browser failure investigations around recorded session events, failure evidence, suggested reproduction plans, reproduction attempts, heuristic confidence assessments, controlled-condition comparisons, and experiment recommendations.

> **Status:** Active development. This repository snapshot contains a FastAPI/SQLite backend, a Manifest V3 Chrome recorder, and a React/Vite dashboard. The dashboard calls the existing API. Automated browser replay is not implemented. Validate the full browser-to-dashboard workflow in your own Chrome profile before presenting it as end-to-end verified.

## Workflow

```text
Project → Session → Browser events → Failure evidence
                                  ↓
                         Reproduction plan
                                  ↓
                         Reproduction attempts
                                  ↓
                         Confidence assessment
                                  ↓
                    Condition comparison / next experiment
                                  ↓
                      Recommendation lifecycle
```

## Technology
- Python, FastAPI, Pydantic
- SQLite
- Chrome Extension Manifest V3
- React, Vite
- Pytest

## Repository layout

```text
TraceForge/
├── main.py
├── replayos.db                 # local runtime database; do not commit
├── requirements.txt
├── extension/
│   ├── manifest.json
│   ├── background.js
│   ├── content.js
│   ├── popup.html
│   └── popup.js
└── frontend/
    ├── package.json
    ├── index.html
    └── src/
        ├── main.jsx
        ├── App.jsx
        └── style.css
```

## Run the backend (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000/docs`.

## Run the dashboard

Open a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal (normally `http://localhost:5173`). The backend CORS allowlist permits the two standard local Vite origins.

If the backend runs at a different URL, create `frontend/.env` from `.env.example` and update `VITE_API_URL`, then restart Vite.

## Load the Chrome extension

1. Start the backend.
2. Open `chrome://extensions`.
3. Enable Developer mode.
4. Choose **Load unpacked** and select the repository's `extension` folder.
5. Create a project and session in the dashboard or API.
6. Open the extension popup and enter the project/session identifiers as requested by the popup.
7. Start recording, then navigate/interact with a test page.
8. Stop recording and refresh the dashboard session.

The extension captures selected navigation, click, JavaScript, promise-rejection and fetch/XHR failure signals according to the code paths in the extension. Browser permissions and page security policies can affect capture. A page reload may require reinjection depending on the current extension implementation.

## Tests

From the repository root:

```powershell
python -m pytest -v
```

The project test files are maintained in the repository. Do not replace your existing test files with this implementation bundle; retain the versions that already pass in your working copy.

## API surface

- `POST /projects`, `GET /projects`
- `POST /projects/{project_id}/sessions`, `GET /projects/{project_id}/sessions`
- `POST /sessions/{session_id}/events`, `GET /sessions/{session_id}/events`
- `GET /sessions/{session_id}/evidence`
- Reproduction-plan generation/list/status endpoints
- Reproduction-attempt create/list/compare endpoints
- Confidence assessment endpoint
- Next-experiment recommendation endpoint
- Experiment-recommendation create/list/status/evaluation endpoints

For exact request and response schemas, use `/docs`.

## Confidence score: interpretation

The score is a deterministic engineering heuristic, not a probability and not proof of a root cause. The dimensions in the current backend are repeatability (40), context (20), plan quality (20), and outcome consistency (20). Read the component breakdown and missing-evidence reasons; do not use the total score alone to make a production decision.

## Important limitations and honest claims

- A reproduction plan is a suggested manual procedure; it is not an automated browser replay.
- The confidence score is not statistically calibrated.
- Comparing recorded conditions identifies differences/unknowns; observational differences do not establish causation.
- The extension does not capture every browser event or every network mechanism.
- The dashboard is an API client; a complete integration test across Chrome, extension, backend, SQLite and UI remains necessary.
- Local development CORS origins are explicitly allowlisted; this is not a production deployment configuration.
- Event data may contain URLs and page-derived text. Use only test accounts/data, avoid sensitive pages, and inspect stored records before sharing a database or demo recording.

## Before a public demo

1. Use a fresh test project and session with synthetic data.
2. Verify the extension start/stop lifecycle and reload behaviour.
3. Verify that navigation, click and failure events appear once (not duplicated).
4. Generate a plan and confirm source-event references.
5. Record reproduced, not-reproduced and inconclusive attempts.
6. Compare attempts and inspect the causality warning.
7. Test the dashboard against the same session.
8. Run the complete pytest suite and record the actual output.
9. Remove local databases, browser profiles, credentials and personal data from any public repository.

## Project philosophy

Debugging should be based on evidence, not guesswork. TraceForge aims to make the path from observing a browser failure to planning, recording and reviewing an investigation more structured and transparent.

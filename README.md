# TraceForge
### Making Browser Failure Investigation More Structured and Evidence-Driven

TraceForge is a browser failure investigation project designed to help developers organize the process of understanding and investigating browser-related failures.

When something breaks in a browser, the error message is often only the beginning. Developers may need to examine what happened before the failure, identify which evidence is available, work out how to reproduce the issue, and determine whether the results support a reliable conclusion.

TraceForge brings these activities into a structured workflow. It connects browser-session events, failure evidence, suggested reproduction plans, reproduction attempts, and heuristic confidence assessments in one place.

The idea behind the project is straightforward: **debugging should be based on evidence, not guesswork.**

> **Project status:** Active development. The current implementation provides a backend prototype for organizing failure investigations. Automated browser replay and complete end-to-end browser validation are not yet established.

---

## Table of Contents

- [Why TraceForge?](#why-traceforge)
- [What It Does](#what-it-does)
- [How It Works](#how-it-works)
- [Core Features](#core-features)
- [Technology Stack](#technology-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Running the Application](#running-the-application)
- [Running Tests](#running-tests)
- [API Overview](#api-overview)
- [Understanding Confidence Scores](#understanding-confidence-scores)
- [Current Limitations](#current-limitations)
- [Planned Improvements](#planned-improvements)
- [Project Philosophy](#project-philosophy)

---

## Why TraceForge?

Browser failures can be difficult to investigate because the information needed to understand them is not always available in one place.

For example, a page might fail to load data, a request might not complete, or a workflow might behave differently when repeated. Knowing that an error occurred does not necessarily explain why it happened.

A useful investigation needs to answer several questions:

- What happened during the session?
- What was recorded immediately before the failure?
- Is there enough evidence to investigate the issue?
- Which steps could help reproduce the failure?
- What happened when those steps were attempted?
- Does the collected evidence support a conclusion, or is more investigation needed?

Without a consistent process, developers can end up repeating the same checks, losing useful context, or treating an assumption as a confirmed root cause.

TraceForge explores a more organized approach by keeping the investigation's available context, suggested steps, and recorded outcomes connected.

## What It Does

TraceForge organizes a failure investigation around a series of related records.

A project can contain sessions, sessions can contain events, and a selected failure can be associated with evidence, reproduction plans, and reproduction attempts.

This structure makes it easier to review the investigation as a sequence of steps rather than treating every error as an isolated incident.

The current backend focuses on:

- Organizing projects and sessions
- Recording and retrieving session events
- Retrieving available failure evidence
- Generating suggested reproduction plans
- Recording reproduction outcomes
- Linking attempts to their corresponding plans
- Producing a heuristic confidence assessment

The backend provides the foundation for a more complete debugging tool while leaving room for stronger browser integration and automated reproduction in future development.

---

## How It Works

The main investigation workflow follows these stages:

```text
Project
   |
   v
Session
   |
   v
Recorded Events
   |
   v
Failure Evidence
   |
   v
Reproduction Plan
   |
   v
Reproduction Attempt
   |
   v
Confidence Assessment
```

### Step 1: Create a project

A project provides a place to organize related investigations.

### Step 2: Create a session

A session represents the workflow or activity being investigated.

### Step 3: Record session events

Events capture information associated with the session. Their usefulness depends on what data is actually recorded.

### Step 4: Review failure evidence

The backend retrieves available failure-related information and relevant recorded events to provide context for the investigation.

### Step 5: Generate a reproduction plan

TraceForge generates suggested steps to guide manual investigation of a selected failure. The plan can also identify information that is still missing.

### Step 6: Record a reproduction attempt

After carrying out the investigation, an attempt can be recorded with its outcome and optional notes. An attempt can also be linked to the plan used.

### Step 7: Review the confidence assessment

The backend evaluates the available investigation data using a heuristic scoring approach. If the evidence is insufficient, the assessment can remain unassessed rather than implying a conclusion that the results do not support.

---

## Core Features

### 1. Project and Session Management

Projects and sessions provide a consistent structure for organizing investigation data. Instead of keeping related information disconnected, the backend associates events and investigation records with their relevant sessions.

### 2. Session Event Recording

The API supports storing and retrieving session events, including event types and associated event data.

These records provide the context needed to investigate a failure. The quality of that context depends on which events and details have been captured.

### 3. Failure Evidence Retrieval

TraceForge provides an endpoint for retrieving recorded evidence associated with a session.

This helps an investigator understand what information is available before deciding how to proceed. Missing evidence can be just as important as recorded evidence because it highlights what still needs to be checked.

### 4. Suggested Reproduction Plans

The backend can generate a structured plan for investigating a selected failure.

A plan may include navigation and manual verification steps, together with notes about missing information.

These steps are suggestions for an investigator to follow. The current backend does not automatically execute the plan or guarantee that following it will reproduce the failure.

### 5. Reproduction Attempt Tracking

TraceForge records the outcome of an investigation attempt. Supported outcomes include:

- `reproduced` — the failure was reported as reproduced during the attempt.
- `not_reproduced` — the failure was reported as not reproduced.
- `inconclusive` — the attempt did not establish a clear result.

Attempts can be linked to a reproduction plan, helping preserve the relationship between the proposed investigation steps and the recorded outcome.

### 6. Heuristic Confidence Assessment

The backend evaluates available investigation data using a rule-based scoring model.

The assessment considers factors such as repeatability, context, reproduction-plan quality, and consistency of outcomes.

The score is intended to summarize the strength of the recorded evidence. It is not a statistically calibrated probability that the root cause is correct.

### 7. Regression Tests

The project includes automated tests for important confidence-assessment behaviours and reproduction-plan linkage.

The current tests cover cases such as inconclusive attempts, conflicting outcomes, and attempts that should not be attributed to the wrong plan.

---

## Technology Stack

| Technology | Role |
|---|---|
| Python | Application logic |
| FastAPI | HTTP API and request handling |
| SQLite | Local data persistence |
| Pytest | Automated regression testing |
| Chrome Extension Manifest V3 | Browser extension component in the `extension/` directory |

FastAPI also provides interactive API documentation, which makes it easier to inspect endpoints and test requests during development.

SQLite keeps the local prototype lightweight without requiring a separate database server.

---

## Project Structure

The repository currently contains the following main files and directories:

```text
TraceForge/
├── extension/          # Chrome extension project files
├── main.py             # FastAPI backend
├── test_confidence.py  # Confidence assessment tests
├── README.md           # Project documentation
└── .gitignore          # Files excluded from Git
```

Other files, including the local virtual environment and SQLite database files, may exist during development. They should not be committed to the public repository unless there is a specific, safe reason to include them.

---

## Getting Started

### Prerequisites

Before running TraceForge, make sure you have:

- Python installed
- pip available
- PowerShell on Windows, or an equivalent terminal
- The project files available locally

### 1. Open the project directory

Open the `TraceForge` folder in VS Code and open its integrated terminal.

### 2. Create a virtual environment

```powershell
python -m venv .venv
```

### 3. Activate the virtual environment

On Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 4. Install the required packages

```powershell
python -m pip install fastapi uvicorn pytest
```

These commands install the main packages needed to run the documented backend and regression tests. If the project later includes a verified `requirements.txt`, use that file to install its complete dependency set.

---

## Running the Application

From the project root, start the FastAPI development server:

```powershell
uvicorn main:app --reload
```

Once the server starts, open the following address in your browser:

**API documentation:** http://127.0.0.1:8000/docs

The interactive documentation lets you inspect available endpoints, review their request models, and send API requests without needing a separate API client.

To stop the development server, press `Ctrl+C` in the terminal where it is running.

---

## Running Tests

Run the current regression test suite with:

```powershell
python -m pytest -v
```

The six confidence-assessment tests passed during the previous development run. The test suite should be run again in the current environment to verify the latest code.

The existing tests cover:

- Returning an unassessed result when no attempts exist
- Handling attempts that are all inconclusive
- Reporting conflicting reproduction outcomes
- Preventing an inconclusive plan from receiving high confidence
- Matching attempts to the correct reproduction plan
- Excluding unlinked attempts from plan-specific attribution

These tests verify specific backend behaviours. They do not prove that every feature is fully tested or that browser-level reproduction works end to end.

---

## API Overview

The backend exposes endpoints for working with projects, sessions, events, evidence, reproduction plans, attempts, and confidence assessments.

| Endpoint | Purpose |
|---|---|
| `/projects` | Create and retrieve projects |
| `/projects/{project_id}/sessions` | Create and retrieve sessions |
| `/sessions/{session_id}/events` | Record and retrieve session events |
| `/sessions/{session_id}/evidence` | Retrieve available session evidence |
| `/sessions/{session_id}/failures/{failure_event_id}/reproduction-plan` | Generate a suggested reproduction plan |
| `/sessions/{session_id}/reproduction-plans` | Retrieve reproduction plans |
| `/sessions/{session_id}/reproduction-plans/{plan_id}/status` | Update reproduction-plan status |
| `/sessions/{session_id}/reproduction-attempts` | Record and retrieve reproduction attempts |
| `/sessions/{session_id}/failures/{failure_event_id}/confidence` | Retrieve a confidence assessment |

For exact request formats, supported values, and response structures, use the interactive API documentation at `/docs`.

**API design note:** In the current implementation, the reproduction-plan endpoint uses a `GET` request while creating and saving a plan. Since `GET` requests are generally expected to retrieve data rather than create resources, this endpoint should be reviewed as the API evolves.

---

## Understanding Confidence Scores

TraceForge uses a heuristic model to summarize the available evidence for an investigation.

The scoring dimensions are:

| Dimension | Maximum contribution |
|---|---:|
| Repeatability | 40 points |
| Context | 20 points |
| Plan quality | 20 points |
| Outcome consistency | 20 points |
| **Total** | **100 points** |

The score is an engineering heuristic, not a probability that a failure's root cause has been correctly identified.

A high score should not replace technical verification, and a recorded attempt should not automatically be treated as proof. When results conflict or evidence is insufficient, the assessment should reflect that uncertainty.

For example, an inconclusive attempt means that the investigation has not established a clear outcome. It should not be interpreted as confirmation that the failure can or cannot be reproduced.

The purpose of confidence assessment is to make the state of the investigation easier to review—not to create certainty where the evidence does not support it.

---

## Current Limitations

TraceForge is an active prototype, and its current implementation focuses on structuring the investigation workflow.

The following limitations should be understood:

- Reproduction plans provide suggested steps; the backend does not automatically execute them.
- A generated plan does not guarantee successful reproduction.
- The quality of an investigation depends on the completeness of the recorded events and evidence.
- Root-cause confirmation still requires appropriate technical verification.
- Confidence scores are heuristic indicators and are not statistically calibrated probabilities.
- The Chrome extension's complete integration with the backend must be validated separately.
- Broader API integration and browser-level end-to-end testing remain areas for further development.

Being explicit about these boundaries helps keep the project technically honest while providing a clear direction for future work.

---

## Planned Improvements

The next stages of development can focus on making investigations more complete, repeatable, and easier to validate.

### Better browser integration

Verify the complete flow from browser event collection through backend storage and evidence retrieval.

### Richer failure evidence

Capture additional details where available, such as request URLs, HTTP methods, response status codes, timestamps, and relevant browser context.

### More reliable reproduction workflows

Improve the structure of suggested reproduction steps and add ways to validate recorded outcomes against actual browser behaviour.

### More explainable confidence assessments

Make it easier to understand how individual scoring dimensions and recorded outcomes affect the final assessment.

### Broader automated testing

Add API integration tests and browser-level end-to-end tests alongside the existing confidence-assessment tests.

### Reproducible setup

Maintain a verified dependency file and document the supported development environment.

### A practical demonstration

Add screenshots or a short demo showing a real investigation moving from recorded events to evidence, reproduction attempts, and a final assessment.

These are planned improvements, not claims about features that are already complete.

---

## Project Philosophy

A useful debugging tool should do more than report that something went wrong. It should help developers understand the available evidence, organize the next steps, and recognize when an investigation remains incomplete.

TraceForge is built around that principle.

By connecting events, evidence, reproduction plans, and recorded outcomes, the project establishes a foundation for more disciplined browser failure investigation.

The long-term goal is to make the path from observing a failure to understanding it more systematic, repeatable, and transparent.

---

**Project:** TraceForge  
**Category:** Developer tools / debugging  
**Status:** Active development  
**Primary focus:** Evidence-driven browser failure investigation

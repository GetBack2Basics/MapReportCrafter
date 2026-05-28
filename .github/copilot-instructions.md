# FunGIS Project Copilot Instructions

Use these instructions for every chat in this repository.

## Environment Ground Truth
- This project is edited over SSH on a remote Linux host. Treat all paths and processes as remote host resources, not local desktop resources.
- Working repository root: /home/ubuntu/fungis-app
- Main frontend page is served from host port 8080.
- Main Flask API is served from host port 5000.
- PostgreSQL/PostGIS-backed tile services may be present separately (for example tileserv on 7800).
- Kubernetes may exist, but browser traffic for this app can still hit host-level processes directly.

## No-Guessing Rule
- Never assume which process is serving a port.
- Before changing runtime behavior, verify live listeners and process owners using commands like ss, pgrep, ps, and curl.
- Validate externally reachable endpoints, not only in-pod endpoints.

## Runtime and Access Checks
- When diagnosing map or API issues, always check both:
  - Host listener state (ss -ltnp, process command line)
  - HTTP behavior from the real client path (curl against host IP and active port)
- If results differ between pod-local and host-local requests, prioritize fixing host listener/routing first.

## Command Execution Policy
- Prefer executing safe, non-destructive diagnostic commands immediately without pausing for extra confirmation.
- Prefer execution_subagent for multi-step command workflows and summarized output.
- Use run_in_terminal only when full/raw output or interactive handling is necessary.
- If sandbox errors show Operation not permitted or blocked network/file access, rerun unsandboxed with a short reason.
- For all git operations, explicitly target the repo root with `git -C /home/ubuntu/fungis-app ...` instead of relying on current working directory.

## Retry and Recovery Limits
- Do not loop repeatedly on the same failing command pattern.
- Maximum retries for the same command pattern: 2.
- On second failure, switch strategy (different command/path/approach).
- Maximum attempts for one issue path before escalation: 3.
- After 3 unsuccessful attempts, stop and present what was tried, what failed, and the next best option.

## Editing and Safety Rules
- Make the smallest practical change set.
- Do not revert unrelated user changes.
- Avoid destructive commands unless explicitly requested.
- After code edits, run a quick validation (lint/errors or endpoint check relevant to the change).

## Project-Specific Defaults
- For bushfire and soil report performance, prefer batched local intersect APIs over many per-layer sequential calls.
- Prefer vector tiles for large bushfire rendering workflows.
- Keep API base resolution compatible with host:5000 unless user explicitly changes deployment routing.
- For index.html UI edits, preserve and maintain build labeling in the footer as: Build YYYY-MM-DD HH:MM (v1.0.0).
- Update the build date/time and version only for pushed builds (not for every local edit).

## Coordination With Existing Project Rules
- Also follow HERMES_RULES.md in this repository.
- If there is any conflict, use this precedence:
  1. Explicit user instruction in current chat
  2. These copilot instructions
  3. HERMES_RULES.md

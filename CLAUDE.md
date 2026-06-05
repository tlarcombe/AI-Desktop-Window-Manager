# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Goal

An AI-powered hybrid tiling/stacking window manager for Linux desktops. The AI observes open windows on the current workspace and arranges them for maximum efficiency, with the active window taking centre stage. Key behaviours:

- **Active window prominence**: the focused window is given the largest/most central position
- **Smart layout**: remaining windows tile around it based on usage patterns and context
- **Fixed positions**: individual windows (or window classes) can be pinned to a fixed position, either per-workspace or across all workspaces
- **Eye tracking (optional)**: webcam input may be used to detect gaze and infer the active window before focus changes

## Architecture Overview

The system is split into three layers:

### 1. Display Protocol Layer
Abstracts over X11 and Wayland so the core logic is protocol-agnostic:
- **X11 backend**: uses EWMH/ICCCM via `python-ewmh` / `python-xlib`, or `x11rb` (Rust)
- **Wayland backend**: uses a compositor-side plugin (wlroots-based) or `wlr-foreign-toplevel-management` protocol
- Emits a normalised stream of window events: `opened`, `closed`, `focused`, `moved`, `resized`, `workspace_changed`

### 2. Layout Engine
Receives window events and produces layout decisions:
- Maintains a window registry (id → metadata: class, title, geometry, workspace, fixed-position rules)
- Calls the **AI planner** to compute an optimal arrangement whenever layout is dirty
- Applies fixed-position overrides after AI output
- Sends `move_resize` commands back to the Display Protocol Layer

### 3. AI Planner
Decides how to tile/stack windows:
- Input: list of windows with metadata, screen geometry, user preference rules
- Output: target geometry for each window
- Implementation options (to be decided): rule-based heuristics, reinforcement learning, or an LLM called via the Anthropic API
- Must be fast enough for real-time re-layout on focus change (target < 200 ms)

### Eye Tracking Module (optional)
- OpenCV + MediaPipe or a dedicated library (e.g. `GazeTracking`)
- Runs as a separate process and publishes gaze events over a local socket
- Layout Engine can treat a sustained gaze on a window as a soft focus signal

## Technology Choices (to be finalised)

| Concern | Candidates |
|---------|-----------|
| Language | Python (fastest iteration), Rust (performance) |
| X11 bindings | `python-ewmh`, `python-xlib`, `x11rb` |
| Wayland | `wlr-foreign-toplevel-management`, custom compositor plugin |
| AI planner | Anthropic Claude API, local ONNX model, heuristic rules |
| Eye tracking | OpenCV + MediaPipe, GazeTracking, Tobii SDK |
| Config format | TOML |
| IPC | Unix socket with JSON-LD or MessagePack |

## Commands

```bash
# Install (editable, with dev tools)
pip install -e ".[dev]"

# Run the daemon
aidwm start
aidwm start --config /path/to/config.toml --verbose

# Control a running daemon
aidwm reload
aidwm status

# Run all tests
pytest

# Run a single test file
pytest tests/test_heuristic_planner.py

# Run a single test by name
pytest -k "test_active_window_gets_left_fraction"

# Lint
ruff check aidwm tests

# Type check
mypy aidwm

# Auto-fix lint issues
ruff check --fix aidwm tests
```

## Configuration Model

Window rules are per-window-class or per-title-pattern and support:
- `fixed_position`: geometry that is never overridden by the layout engine
- `fixed_across_workspaces`: same fixed geometry applied on every workspace
- `priority`: hint to the AI planner about relative importance
- `always_on_top` / `always_tiled`

## Key Constraints

- Must not require the user to replace their existing compositor/WM; prefer running as a layer on top (e.g. using EWMH hints under X11, or a Wayland IPC protocol)
- Re-layout must complete in under 200 ms to feel instantaneous
- Eye tracking must degrade gracefully when no webcam is present
- The AI planner must fall back to a deterministic heuristic if the API or model is unavailable

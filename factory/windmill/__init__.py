from __future__ import annotations

"""Windmill integration layer (future).

Windmill (https://github.com/windmill-labs/windmill) is an AGPL-licensed,
Python-native workflow engine with visual drag-and-drop editing and
a built-in WebUI management dashboard.

Current status: Using the built-in workflow engine
(factory/workflow/engine.py). When the project reaches a scale that
requires a full workflow platform, this module will provide the adapter
layer to replace the built-in engine with Windmill as a drop-in replacement.

Integration plan:
- factory/windmill/client.py — Windmill REST API client
- factory/windmill/adapter.py — WorkflowTemplate → Windmill Flow converter
- factory/windmill/executor.py — Windmill Flow executor (replaces engine.py)
"""

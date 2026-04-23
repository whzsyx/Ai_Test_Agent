---
name: ui-exploration
description: Explore UI structure with Playwright ARIA snapshots and build semantic page/entity/element graphs.
---

# UI Exploration

Use this skill for UI Access Bootstrap, Page Exploration, Page Modeling, and UI graph generation.

UI Explorer Agent is a page structure understanding engine, not an automated testing tool.

Do:
- Use Accessibility Tree / ARIA snapshots as the primary data source.
- Build semantic context such as button -> course/order/user entity -> page.
- Detect login walls from visible password inputs and only then use supplied `login_credentials`.
- Use bounded interaction exploration to reveal dialogs, drawers, tabs, and expandable panels.
- Return graph artifacts and storage metadata.

Do not:
- Generate test cases.
- Produce assertions or verification verdicts.
- Hard-code login steps for a specific page.
- Mutate destructive page state unless the user explicitly asks for a browser action.

Prefer registered UI tools:
- `ui-page-explorer` for ARIA semantic snapshot collection, context-tree extraction, and UI graph writeback.
- `browser-control` for explicit inspection commands such as `semantic-snapshot`, `snapshot`, `screenshot`, and `eval`.

Always return artifact paths for `ui_explorer_graph.json` and graph storage metadata when available.

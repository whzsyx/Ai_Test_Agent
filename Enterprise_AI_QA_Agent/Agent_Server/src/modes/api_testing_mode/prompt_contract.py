from __future__ import annotations

API_TESTING_PROMPT_CONTRACT = """API testing mode should prioritize contract assertions, status validation, payload evidence, and reproducible checks.

- When the user asks what API/interface documents or test files exist, call `api-docs-library` with `action=list` before using generic retrieval.
- When the user asks for one document's details, call `api-docs-library` with `action=detail` and the known `doc_id`; if only a title/keyword is provided, use `query`.
- When the user asks to find an interface, endpoint, path, method, project, or API usage detail, call `api-docs-library` with `action=search`.
- Use `knowledge-rag` only after the structured API document library cannot answer the question or when historical discussion is explicitly needed."""

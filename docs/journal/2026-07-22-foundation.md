# Development Journal

Record architectural decisions, experiments, and learnings here.

## 2026-07-22 — Project Foundation

- Initialized project structure with FastAPI backend and Next.js frontend
- Established engine module boundaries with placeholder interfaces
- Configured Docker Compose with PostgreSQL, Redis, Celery, backend, and frontend
- Set up CI pipeline with Ruff linting and Pytest
- Created root `ARCHITECTURE.md` as living design document

## 2026-07-27 — Evidence Engine (Milestone 2)

- Implemented scoring module with default weights (sum to 100) and weighted calculator
- Built Evidence Engine with pluggable collectors and stub evidence from all engine categories
- Added `EvidenceSnapshot` ORM model and Alembic migration
- Exposed evidence API: accumulate, persist, latest snapshot, snapshot by ID
- Wired dashboard asset summaries to live evidence confidence scores
- Added evidence detail panel on frontend asset pages
- 15 backend tests passing

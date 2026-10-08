# Decision Log

Append-only. Format: `YYYY-MM-DD | Decision | Reason`

---

| Date | Decision | Reason |
|---|---|---|
| 2026-10-08 | Next.js App Router at project root, FastAPI backend under `backend/` | Simpler monorepo layout; avoids double nesting |
| 2026-10-08 | Flat backend module structure (`backend/core/`, `backend/ingest/`, etc.) | Cleaner imports, less nesting than `backend/analyx/` |

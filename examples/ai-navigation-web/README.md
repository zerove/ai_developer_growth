# AI Navigation Web

Web UI for the AI Developer Growth knowledge base. Built with FastAPI + Jinja2 + SQLite.

## Features

- **User Authentication**: Register, login, JWT cookie-based sessions
- **Dashboard**: Overview of learning progress, assessment scores, contributions
- **Skill Assessment**: 5-dimension skill evaluation with recommendations
- **Learning Progress**: Track document reading with status management
- **Content Contributions**: Submit and manage documentation contributions

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Framework | FastAPI + Starlette |
| Templates | Jinja2 |
| Database | SQLite + aiosqlite |
| Auth | bcrypt + python-jose (JWT) |
| Testing | pytest + httpx |

## Quick Start

```bash
cd examples/ai-navigation-web
pip install -e .
uvicorn src.app:app --reload --port 8000
# Open http://localhost:8000
```

## Tests

```bash
python -m pytest tests/ -v
# 8 tests passed
```

## Routes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Home page |
| GET/POST | `/auth/register` | Registration |
| GET/POST | `/auth/login` | Login |
| GET | `/auth/logout` | Logout |
| GET | `/dashboard` | User dashboard |
| GET/POST | `/assess` | Skill assessment |
| GET | `/assess/history` | Assessment history |
| GET | `/progress` | Learning progress |
| POST | `/progress/start` | Start learning doc |
| POST | `/progress/{id}/complete` | Mark as completed |
| GET | `/contribute` | My contributions |
| GET/POST | `/contribute/new` | New contribution |

## Database Schema

- **users**: id, username, email, password_hash, created_at
- **assessments**: user_id, 5 skill scores, overall, created_at
- **learning_progress**: user_id, doc_path, status, timestamps
- **contributions**: user_id, doc_path, content, status, timestamps

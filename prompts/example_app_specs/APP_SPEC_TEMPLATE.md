# [Project Name] - App Specification

## Overview

[2-4 sentences describing what this app does, who it's for, and the core value proposition.]

---

## Tech Stack

- **Frontend**: [Framework + version] (e.g., React 19 with Vite, Next.js 14+, Vanilla HTML/CSS/JS)
- **Styling**: [CSS approach] (e.g., Tailwind CSS + Shadcn/ui, vanilla CSS)
- **Backend**: [Framework] (e.g., FastAPI, Express, none)
- **Database**: [DB choice] (e.g., PostgreSQL, SQLite, localStorage)
- **Package Manager**: [Tool] (e.g., bun, pnpm, npm, uv)
- **LLM/AI**: [If applicable] (e.g., Claude via Anthropic API, OpenRouter)
- **Real-time**: [If applicable] (e.g., SSE, WebSockets)

---

## Environment Setup

### Prerequisites
- [Runtime requirements] (e.g., Node.js 20+, Python 3.11+)
- [Package managers] (e.g., bun installed globally)
- [External services] (e.g., PostgreSQL running, API keys)

### Configuration
- Frontend dev server: port [PORT] (specify if default 3000 is taken)
- Backend server: port [PORT]
- Environment variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `API_KEY` | Yes | [What it's for] |
| `DATABASE_URL` | Yes | [Connection string] |
| `PORT` | No | [Default: 8000] |

[Note: If .env exists at a relative path, mention it: "../../.env contains these variables. Copy to project root."]

---

## Architecture

[ASCII diagram showing the major components and how they communicate. This helps the coding agent understand the system structure before writing any code.]

```
┌─────────────────────────────────┐
│         Frontend (React)         │
│   ┌──────────┐  ┌──────────┐   │
│   │  Pages   │  │Components│   │
│   └──────────┘  └──────────┘   │
└──────────────┬──────────────────┘
               │ REST API / SSE
┌──────────────┴──────────────────┐
│         Backend (FastAPI)        │
│   ┌──────────┐  ┌──────────┐   │
│   │ Routes   │  │ Services │   │
│   └──────────┘  └──────────┘   │
└──────────────┬──────────────────┘
               │
┌──────────────┴──────────────────┐
│         Database (PostgreSQL)    │
└─────────────────────────────────┘
```

---

## Core Features

[List features as numbered sections. Each feature becomes a Linear issue. Include enough detail for the coding agent to implement without ambiguity.]

### Feature 1: [Name]
**Description**: [What this feature does]
**Requirements**:
- [Specific requirement]
- [Specific requirement]
- [Specific requirement]

**Test Steps** (the coding agent will verify these):
1. [How to verify this works]
2. [Expected behavior]

---

### Feature 2: [Name]
**Description**: [What this feature does]
**Requirements**:
- [Specific requirement]
- [Specific requirement]

**Test Steps**:
1. [How to verify]
2. [Expected behavior]

---

### Feature 3: [Name]
[Continue pattern...]

---

[TIPS for feature scoping:
- 5-8 features is ideal for a single session
- 10-15 features for a multi-session project
- Each feature should be independently testable
- Order features by dependency (foundational features first)
- Include test steps — the orchestrator passes these to the coding agent]

---

## Data Models

[Define the data layer. Use the format that matches your tech stack.]

### [For SQL databases]
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE items (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    title TEXT NOT NULL,
    status TEXT DEFAULT 'active'
);
```

### [For Pydantic/Python]
```python
class User(BaseModel):
    id: str
    name: str
    email: str
    created_at: datetime

class Item(BaseModel):
    id: str
    user_id: str
    title: str
    status: Literal["active", "archived", "deleted"]
```

---

## API Endpoints

[If the app has a backend, list the endpoints. If frontend-only, remove this section.]

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/items | List all items |
| POST | /api/items | Create item |
| GET | /api/items/:id | Get item by ID |
| PUT | /api/items/:id | Update item |
| DELETE | /api/items/:id | Delete item |

---

## File Structure

[Directory tree showing where code should go. This is very helpful for the coding agent.]

```
project/
├── frontend/               # [or src/, or just root for vanilla]
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── pages/          # Page components
│   │   ├── lib/            # Utilities and helpers
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── index.html
│   ├── package.json
│   └── vite.config.ts
├── backend/                # [or server/, or agent/]
│   ├── main.py             # Entry point
│   ├── routes.py           # API routes
│   ├── models.py           # Data models
│   └── requirements.txt
├── .env
├── README.md
└── init.sh                 # Startup script (required by harness)
```

---

## UI/UX Design

### Design System
- **Theme**: [Dark/Light/Both]
- **Primary color**: [Hex code] (e.g., #3B82F6 blue)
- **Accent color**: [Hex code] (e.g., #ff6347 tomato red)
- **Background**: [Hex code]
- **Text**: [Hex code]
- **Font**: [Font family] (e.g., Inter, system-ui)

### Key Screens

**Screen 1: [Name]**
- [Layout description]
- [Key elements]
- [Interactive behavior]

**Screen 2: [Name]**
- [Layout description]
- [Key elements]

### Key Interactions
1. [User does X] → [System responds with Y]
2. [User does X] → [System responds with Y]

---

## Success Criteria

[Numbered list of measurable criteria. The orchestrator uses these to determine when the project is complete.]

1. [Feature X works as specified]
2. [Feature Y handles edge case Z]
3. [App runs on mobile browsers]
4. [No console errors in normal usage]
5. [All features visually match design system]
6. [Data persists across page refresh] (if applicable)

---

## Constraints & Notes

[Optional section for anything the coding agent needs to know.]

- [e.g., "Single-page app, no routing needed"]
- [e.g., "No external CDN dependencies — bundle everything"]
- [e.g., "Must work offline after initial load"]
- [e.g., "This is a proof of concept — skip auth"]

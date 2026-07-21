# AI Care Operations Optimiser

A prototype AI-native operations layer for domiciliary care route optimisation. The system optimises daily care visit routes for a small fleet of carers and explains the optimisation reasoning through an animated map visualisation.

## Prerequisites

| Requirement | Minimum Version |
|-------------|-----------------|
| Node.js     | 18+             |
| Python      | 3.11+           |
| npm         | 9+ (ships with Node 18) |
| pip         | Latest recommended |

> **Note:** Python 3.11 or 3.12 is recommended. OR-Tools may have compatibility issues with Python 3.14+.

## Quick Start

```bash
# 1. Create and activate a Python virtual environment
python3 -m venv .venv
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows

# 2. Install all dependencies (backend + frontend)
npm run install:all

# 3. Start both servers
npm start
```

The application will be available at:
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API docs**: http://localhost:8000/docs

Both servers start concurrently with a single command and are ready within 30 seconds.

## Project Structure

```
├── backend/            # FastAPI + Python backend
│   ├── app/
│   │   ├── models/     # Pydantic data models
│   │   ├── routes/     # API endpoint handlers
│   │   ├── services/   # Business logic (optimiser, maps client)
│   │   └── db/         # Database schema, repositories, seed data
│   └── tests/          # pytest + Hypothesis property tests
├── frontend/           # React + Vite + Tailwind CSS frontend
│   └── src/
│       ├── components/ # Reusable UI components
│       ├── pages/      # Route-level page components
│       ├── hooks/      # Custom React hooks
│       ├── types/      # TypeScript type definitions
│       └── services/   # API client layer
├── data/               # SQLite database file (auto-created)
└── package.json        # Root scripts for install and start
```

## Installation

Install all dependencies (backend and frontend) with a single command:

```bash
npm run install:all
```

This runs:
- `pip install -r backend/requirements.txt` for the Python backend (FastAPI, OR-Tools, Google Maps, etc.)
- `npm install` in the `frontend/` directory for the React frontend

> **Important:** Ensure your Python virtual environment is activated before running `install:all` so that packages are installed into the venv rather than system-wide.

## Running the Application

Start both the backend and frontend with:

```bash
npm start
```

This launches:
- **Backend**: FastAPI via Uvicorn on `http://localhost:8000` (with hot-reload)
- **Frontend**: Vite dev server on `http://localhost:5173`

The frontend proxies API requests (`/api/*` and `/ws/*`) to the backend automatically.

> **Important:** Ensure your Python virtual environment is activated before running `npm start` so that `uvicorn` and backend dependencies are available.

## Configuration

Before running optimisation, set your Google Maps API key via the Configuration screen in the UI (`/config`), or set the environment variable:

```bash
export GOOGLE_MAPS_API_KEY=your-key-here
```

The API key needs the following Google Maps APIs enabled:
- Distance Matrix API
- Maps JavaScript API

The key is persisted in the SQLite database and survives restarts.

## Running Tests

```bash
# All tests (backend + frontend)
npm test

# Backend only (pytest + Hypothesis)
npm run test:backend

# Frontend only (Vitest + fast-check)
npm run test:frontend
```

## Available Scripts

| Script | Description |
|--------|-------------|
| `npm run install:all` | Install all backend and frontend dependencies |
| `npm start` | Start both servers concurrently |
| `npm run start:backend` | Start only the FastAPI backend |
| `npm run start:frontend` | Start only the Vite frontend |
| `npm test` | Run all tests |
| `npm run test:backend` | Run backend tests (pytest) |
| `npm run test:frontend` | Run frontend tests (Vitest) |

## Tech Stack

- **Backend**: Python 3.11+, FastAPI, Google OR-Tools (VRP solver), SQLite, aiosqlite
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS, Google Maps JS API
- **Testing**: pytest + Hypothesis (backend), Vitest + fast-check (frontend)
- **Dev tooling**: concurrently (parallel process runner)

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `uvicorn: command not found` | Activate your Python virtual environment: `source .venv/bin/activate` |
| `ModuleNotFoundError` on start | Run `npm run install:all` with the venv activated |
| Frontend fails to connect to API | Ensure the backend is running on port 8000 |
| Google Maps errors | Set your API key via `/config` or the environment variable |
| OR-Tools import error | Ensure you're using Python 3.11 or 3.12 (not 3.14+) |

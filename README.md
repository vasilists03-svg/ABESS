# ABESS — Argumentation-Based Equation-Solver Selector

ABESS is a web application for selecting mathematical equation-solving
methods and computing solutions.

The application supports manual method selection and automatic
recommendations through the external rAIson platform.

## Technologies

- Backend: Python, FastAPI, Pydantic
- Mathematical processing: SymPy, SciPy
- Frontend: HTML, CSS, JavaScript, Plotly.js
- Database: SQLite, SQLAlchemy
- Authentication: Bearer tokens and API keys
- Deployment: Docker, Nginx, Caddy
- External decision service: rAIson

## Supported solving methods

1. Bisection
2. Newton-Raphson
3. Secant
4. fzero (SciPy Brent method)
5. ITP
6. Muller
7. Symbolic Solve
8. Polynomial Roots
9. Integer Exhaustive Scan

## Project structure

- `backend/app/` — FastAPI application and mathematical solver
- `backend/app/routers/` — API endpoints
- `backend/app/services/` — equation solving and rAIson integration
- `backend/app/models/` — database models
- `backend/app/schemas/` — request and response models
- `frontend/` — web interface and administration dashboard

## Configuration

Application configuration is provided through environment variables.

See `.env.example` for the supported variable names.

Real credentials, production databases, and TLS private keys
are not included in this repository.

## Deployment

The application is deployed at https://abess.hmu.gr.

The production deployment uses Docker Compose, FastAPI/Uvicorn,
Nginx and Caddy.

## Academic context

Developed as part of a diploma thesis at the
Hellenic Mediterranean University (HMU).

The rAIson decision service is an external research platform.
The equation-solving functionality is executed by the ABESS backend.

## Local deployment with Docker Compose

A standalone two-service Docker Compose configuration is
provided for local installation.

1. Copy `.env.example` to `.env`.
2. Configure the required authentication, database and
   external-service environment variables.
3. Start the application using `docker compose up --build -d`.
4. Open http://localhost:8080.

The local configuration exposes the frontend only on the
host's loopback interface. The backend remains internal
to the Docker network.

The local setup does not include the production Caddy
HTTPS reverse proxy or production credentials.

The application requires valid configuration before
it can be used fully. Automatic method selection depends
on access to the external rAIson service.

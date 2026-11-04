import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine

from app.routers import admin
from app.routers import auth
from app.routers import equation

# Import models so SQLAlchemy knows all tables.
from app.models.guest_usage import GuestUsage
from app.models.solve_history import SolveHistory
from app.models.user import User


load_dotenv()


# Create SQLite tables if they do not already exist.
Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="Equation Solver API",
    description=(
        "Backend API for equation solving, "
        "authentication and guest usage limit."
    ),
    version="1.0.0",
    root_path="/api",
)


# CORS
frontend_url = os.getenv(
    "FRONTEND_URL",
    "",
).strip().rstrip("/")

allowed_origins = []

if frontend_url:
    allowed_origins.append(frontend_url)


app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Routers
app.include_router(auth.router)
app.include_router(equation.router)
app.include_router(admin.router)


@app.get("/health")
def health_check():
    return {
        "status": "Backend is running"
    }
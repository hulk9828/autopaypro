# Auto Loan Pro Backend

This is a FastAPI-based backend for an Auto Loan / Payment Management system.

## Tech Stack

- Python 3.12
- FastAPI (async)
- SQLAlchemy 2.0 (async)
- asyncpg
- PostgreSQL (Docker for local, Supabase for cloud)
- Alembic (async migrations)
- JWT auth using `python-jose`
- Password hashing using `passlib[bcrypt]`
- Pydantic v2
- Docker & Docker Compose
- Clean architecture

## Project Structure

```
payment_app/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── security.py
│   │   └── deps.py
│   ├── api/
│   │   └── v1/
│   │       ├── api_router.py
│   │       ├── health.py
│   │       └── customers/
│   │           ├── router.py
│   │           ├── service.py
│   │           └── schemas.py
│   ├── models/
│   │   ├── enums.py
│   │   ├── user.py
│   │   ├── vehicle.py
│   │   ├── customer.py
│   │   ├── customer_vehicle.py
│   │   └── loan.py
│   └── __init__.py
├── alembic/
│   └── env.py
├── alembic.ini
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── .env.example
├── requirements.txt
└── README.md
```

## Getting Started

### 1. Environment Variables

Create a `.env` file in the `payment_app/` directory based on the `.env.example` (which is not included in the repository due to security reasons, but the contents should be similar to):

```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/payment_db
SECRET_KEY=your_super_secret_key
ENVIRONMENT=development
ACCESS_TOKEN_EXPIRE_MINUTES=30
ALGORITHM=HS256
```

For Supabase, the `DATABASE_URL` should include `sslmode=require` (e.g., `postgresql+asyncpg://user:password@host:port/database?sslmode=require`).

### 2. Docker Setup

Navigate to the `payment_app/docker` directory and build the Docker images:

```bash
docker compose build
```

Then, run the services:

```bash
docker compose up
```

This will start the FastAPI application and a PostgreSQL database. The FastAPI application will be accessible at `http://localhost:8000`.

### 3. Database Migrations (using Alembic)

To run migrations inside the `app` container (assuming it's running via `docker compose up`):

```bash
docker compose exec app alembic revision --autogenerate -m "Initial migration"
docker compose exec app alembic upgrade head
```

Replace "Initial migration" with an appropriate message for your migration.

### 4. Health Check

Access the health check endpoint:

```
GET http://localhost:8000/api/v1/health
```

This should return: `{ "status": "ok" }`

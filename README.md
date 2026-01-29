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

This will start the FastAPI application and a PostgreSQL database. The FastAPI application will be accessible at `http://localhost:8218`.

### 3. Database Migrations (using Alembic)

To run migrations inside the `app` container (assuming it's running via `docker compose up`):

```bash
docker compose exec app alembic revision --autogenerate -m "Initial migration"
docker compose exec app alembic upgrade head
```

Replace "Initial migration" with an appropriate message for your migration.

### 4. Health Check

The app runs on **port 8218**. Access the health check endpoint:

- From the server: `http://localhost:8218/api/v1/health`
- From outside: `http://<server-ip-or-hostname>:8218/api/v1/health`

This should return: `{ "status": "ok" }`.

---

## Accessing the app from outside the server

If the app works with `curl` on the server but **not from your browser or another machine**, the blocker is almost always the **AWS Security Group** (or another cloud firewall). Use the steps below.

### 1. Confirm the app and port on the server

On the server run:

```bash
# Should return: {"status":"ok"}
curl -s http://127.0.0.1:8218/api/v1/health

# Check something is listening on 8218
ss -tlnp | grep 8218
# or: sudo lsof -i :8218
```

If these work, the app is fine. The issue is network/firewall between the internet and your server.

### 2. Open port 8218 in AWS (required on EC2)

- **AWS Console** → **EC2** → **Instances** → select your instance.
- Note the **Security group** (e.g. `sg-xxxxx`) and click it.
- **Inbound rules** → **Edit inbound rules** → **Add rule**:
  - **Type:** Custom TCP
  - **Port range:** `8218`
  - **Source:** Your IP (recommended) or `0.0.0.0/0` (anywhere)
- **Save rules**.

Without this rule, traffic to port 8218 is dropped (you'll see "Connection timed out" from outside or when curling the public IP from the server). You can confirm with `bash scripts/check-access.sh` on the server.

### 3. Use the server’s public IP (not localhost)

From your laptop/browser use the **public IP or hostname** of the EC2 instance, not `localhost`:

```bash
# On the server, get your public IP (for your info)
curl -s http://checkip.amazonaws.com
```

Then from outside: `http://<that-public-ip>:8218/api/v1/health` or `http://<that-public-ip>:8218/docs`.

### 4. If it still fails

- **UFW on the server:** If you use `ufw`, allow the port: `sudo ufw allow 8218/tcp` then `sudo ufw reload` (and ensure `ufw status` shows 8218 allowed).
- **Wrong URL:** Use `http://` (not `https://`) unless you have TLS in front. Port must be `:8218`.
- **Timeout vs connection refused:** Timeout usually means Security Group or network blocking. Connection refused usually means nothing is listening on that port on the server.

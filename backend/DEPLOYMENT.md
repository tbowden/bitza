# Deployment Guide

Step-by-step instructions for three scenarios:

- [Local development](#local-development) — run directly on your machine
- [Docker — UAT](#docker-uat) — containerised, local or staging server
- [Docker — Production](#docker-production) — containerised, behind nginx reverse proxy

---

## Prerequisites

All three scenarios require:

- **Git** — to clone the repository
- **uv** — Python version and environment manager

Install uv if you don't have it:

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Docker scenarios additionally require:

- **Docker Desktop** (macOS / Windows) or **Docker Engine + Compose plugin** (Linux)

---

## Local Development

### 1. Clone the repository

```bash
git clone <repository-url>
cd assetmgmt
```

### 2. Install dependencies

```bash
uv sync --group dev
```

uv reads `.python-version` (Python 3.11) and `pyproject.toml` automatically
and creates a `.venv` directory. You never need to activate it manually.

### 3. Configure the environment

The `.env.dev` file is already present and safe to use for local development.
Open it and set a real secret key:

```bash
# Generate a secret key
uv run python -c "import secrets; print(secrets.token_hex(32))"
```

Paste the output as the value of `SECRET_KEY` in `.env.dev`.

### 4. Create the database and run migrations

```bash
uv run alembic upgrade head
```

This creates `data/dev.db`.

### 5. Create the superuser

```bash
uv run python -m app.cli create-superuser
```

You will be prompted for email, username, display name, and password.
The password must be at least 12 characters and pass a strength check.
This can only be run once — a second attempt will fail with a clear error.

### 6. Start the server

```bash
uv run uvicorn app.main:app --reload
```

The API is now running at **http://localhost:8000**

- Interactive docs: http://localhost:8000/api/v1/docs
- Health check: http://localhost:8000/health

### 7. Run the tests (optional)

```bash
APP_ENV=test uv run pytest
```

---

## Docker — UAT

Runs the application in a Docker container using the UAT environment.
Suitable for testing on a local machine or a staging server without a
reverse proxy in front of it.

### 1. Clone the repository

```bash
git clone <repository-url>
cd assetmgmt
```

### 2. Configure the UAT environment

```bash
cp .env.uat .env.uat.local   # optional — edit .env.uat directly if preferred
```

Open `.env.uat` and set a real secret key:

```bash
# Generate a secret key
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Paste the output as the value of `SECRET_KEY` in `.env.uat`.

### 3. Add a host port to docker-compose for UAT

The default `docker-compose.yml` does not expose a host port (it expects nginx
to proxy traffic). For UAT without nginx, add a temporary port mapping.

Open `docker-compose.yml` and add a `ports` section under the `app` service:

```yaml
services:
  app:
    ports:
      - "8000:8000"
```

> **Remove this port mapping before a production deployment.**

### 4. Create the Docker network

The compose file expects an external Docker network. Create it once:

```bash
docker network create nginx_proxy_network
```

### 5. Build and start the container

```bash
APP_ENV=uat docker compose up -d --build
```

The container runs migrations automatically on startup.

### 6. Create the superuser

```bash
docker compose exec app uv run python -m app.cli create-superuser
```

### 7. Verify

```bash
# Check the container is healthy
docker compose ps

# Check the logs
docker compose logs app

# Hit the health endpoint
curl http://localhost:8000/health
```

The API is now running at **http://localhost:8000**

### Stopping and restarting

```bash
docker compose down          # stop (data volume is preserved)
docker compose up -d         # restart without rebuilding
docker compose up -d --build # rebuild image and restart
```

---

## Docker — Production

Runs the application in a Docker container behind your existing nginx reverse
proxy. The container is not exposed directly on a public port.

### 1. Clone the repository on the server

```bash
git clone <repository-url>
cd assetmgmt
```

### 2. Create the production environment file

```bash
cp .env.prod.template .env.prod
```

Open `.env.prod` and fill in all values:

```bash
# Generate a secret key
python3 -c "import secrets; print(secrets.token_hex(32))"
```

`.env.prod` must **never** be committed to version control.
It is already listed in `.gitignore`.

Key settings to review in `.env.prod`:

| Setting | Notes |
|---|---|
| `SECRET_KEY` | Required. Generate with the command above. Min 32 chars. |
| `CHECK_PWNED_PASSWORDS` | Set to `true` for public-facing deployments. Requires internet access from the container. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Default 15. Increase for less-sensitive deployments. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Default 30. |

### 3. Configure the Docker network name

Open `docker-compose.yml` and check the network name at the bottom of the file:

```yaml
networks:
  proxy_network:
    external: true
    name: nginx_proxy_network   # ← change this to match your nginx network
```

Find the name of your existing nginx proxy network:

```bash
docker network ls
```

Update the `name:` value to match.

### 4. Configure nginx

Add a location block to your nginx configuration to proxy traffic to the
container. The container is reachable by its name `assetmgmt_app` on the
shared Docker network:

```nginx
location /api/ {
    proxy_pass         http://assetmgmt_app:8000;
    proxy_set_header   Host              $host;
    proxy_set_header   X-Real-IP         $remote_addr;
    proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header   X-Forwarded-Proto $scheme;
}
```

Reload nginx after updating the config:

```bash
docker exec <nginx-container-name> nginx -s reload
```

### 5. Build and start the container

```bash
docker compose up -d --build
```

The container runs migrations automatically on startup and will restart
automatically if the server reboots (`restart: unless-stopped`).

### 6. Create the superuser

```bash
docker compose exec app uv run python -m app.cli create-superuser
```

This is a one-time operation. If you run it again it will exit with an error
telling you a superuser already exists — that is the expected behaviour.

### 7. Verify

```bash
# Container status and health
docker compose ps

# Application logs
docker compose logs app

# Tail logs in real time
docker compose logs -f app

# Health check via nginx
curl https://<your-domain>/health
```

---

## Updating to a new version

For both Docker scenarios:

```bash
git pull
docker compose up -d --build
```

The container runs `alembic upgrade head` automatically on startup, so any
new migrations are applied before the server starts.

To check what migrations will run before deploying:

```bash
docker compose run --rm app alembic history
docker compose run --rm app alembic current
```

---

## Database backup

The SQLite database lives in the `assetmgmt_data` Docker volume. Back it up by
copying the file out of the volume:

```bash
# Find the volume mount path
docker volume inspect assetmgmt_data

# Or copy directly via the container
docker compose exec app cat /app/data/prod.db > backup-$(date +%Y%m%d).db
```

For automated backups, schedule the above `cat` command with cron and copy
the output to a safe location.

---

## Troubleshooting

**Container exits immediately on startup**
```bash
docker compose logs app
```
Most likely cause: `.env.prod` is missing or `SECRET_KEY` has not been set.

**`alembic upgrade head` fails inside the container**

The data directory may not be writable. Check volume permissions:
```bash
docker compose exec app ls -la /app/data
```

**`create-superuser` fails with "superuser already exists"**

This is correct behaviour — only one superuser is permitted. Log in with the
existing superuser credentials. If you have genuinely lost access, connect to
the database directly:
```bash
docker compose exec app python3 -c "
from app.db.session import SessionLocal
from app.models.user import User, UserRole
db = SessionLocal()
su = db.query(User).filter(User.role == UserRole.superuser).first()
print(su.email if su else 'No superuser found')
db.close()
"
```

**Port 8000 already in use (local dev)**
```bash
uv run uvicorn app.main:app --reload --port 8001
```

**Tests fail after pulling new code**
```bash
uv sync --group dev          # update dependencies
APP_ENV=test uv run pytest   # re-run
```

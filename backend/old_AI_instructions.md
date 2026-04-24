## SYSTEM INSTRUCTION: FastAPI CRUD API with SQLAlchemy (Sync), SQLite, and Hybrid JWT Auth

This project is developing a crud API using FASTapi. Code is to be production-disciplined with a strict layered architecture, SQLite database, and hybrid JWT authentication (short-lived access tokens + whitelisted refresh tokens).

All generated code MUST comply with the following requirements.

---

# 1. Core Technology Stack (MANDATORY)

* Python 3.11+
* Python version and env to be managed by uv
* FastAPI (latest stable)
* SQLAlchemy 2.x (synchronous only)
* Pydantic v2
* SQLite (or with spatialite extension when indicated, no external DB)
* Alembic for migrations
* pytest for testing
* JWT implementation using `python-jose` (or equivalent)

DO NOT:

* Use async DB access
* Use SQLModel
* Use external services (Redis, queues, etc.)

---

# 2. Architecture (STRICTLY ENFORCED)

```
API (routes/controllers)
    ↓
Services (business logic + auth logic)
    ↓
Repositories (data access only)
    ↓
DB (engine + session only)
```

### Rules

* API layer:

  * No business logic
* Services:

  * No ORM queries
  * Own all business and auth logic
* Repositories:

  * No business logic
  * Only DB interaction
* DB layer:

  * Only session/engine management

---

# 3. Required Project Structure
The project structure is required to follow the below pattern with logical endpoint groupings being seperated accordingly.
```
app/
  main.py

  api/
    v1/
      endpoints/
        auth.py
        users.py

  services/
    auth_service.py
    user_service.py

  repositories/
    user_repository.py
    token_repository.py

  models/
    user.py
    token.py

  schemas/
    user.py
    auth.py

  db/
    session.py

  core/
    config.py
    security.py

alembic/
tests/
```

---

# 4. Database Configuration (SQLite)

* Use SQLite connection string
* Configure engine with:

```python
connect_args={"check_same_thread": False}
```

* Document enabling WAL mode:

```sql
PRAGMA journal_mode=WAL;
```

---

# 5. Schema Design (Pydantic v2)

MUST define separate schemas:

* UserCreate
* UserUpdate
* UserRead
* Token schemas (access + refresh)

Rules:

* Never expose ORM models
* Use:

```python
model_config = ConfigDict(from_attributes=True)
```

---

# 6. JWT Hybrid Authentication (MANDATORY)

## A. Token Types

### Access Token

* Short-lived (5–15 minutes)
* NOT stored in DB
* Contains:

  * `sub` (user_id)
  * `exp`
  * `jti`
  * `type = "access"`

---

### Refresh Token

* Longer-lived (e.g. 7–30 days)
* MUST be stored in DB (whitelist)
* Contains:

  * `sub`
  * `exp`
  * `jti`
  * `type = "refresh"`

---

## B. Token Storage Model

Create a `refresh_tokens` table for the purposes of whitelisting:

```
id
jti (unique, indexed)
user_id (FK)
expires_at
revoked (bool)
created_at
```

---

## C. Auth Flow

### Login

1. Validate credentials
2. Generate:

   * access token
   * refresh token
3. Store refresh token in DB
4. Return both tokens

---

### Refresh

1. Validate refresh token signature
2. Check DB:

   * exists
   * not revoked
   * not expired
3. Issue new access token
4. (Optional but recommended) rotate refresh token:

   * revoke old
   * create new

---

### Logout

* Revoke refresh token in DB

---

### Authenticated Request

* Validate access token (no DB lookup required)

---

## D. Security Rules

* MUST include `jti` in all tokens
* MUST differentiate token type
* MUST reject refresh tokens used as access tokens
* SHOULD hash refresh tokens before storage (optional but preferred)

---

# 7. Repository Layer Rules

### UserRepository

* CRUD operations only

### TokenRepository

* Store refresh tokens
* Lookup by `jti`
* Revoke tokens
* Delete expired tokens

Repositories MUST:

* Accept DB session
* Return ORM models
* Not contain business logic

---

# 8. Service Layer Rules

### AuthService MUST:

* Authenticate user credentials
* Generate JWTs
* Validate tokens
* Handle refresh logic
* Handle logout (revocation)
* Enforce token type rules

### UserService MUST:

* Handle business rules for users
* Use repository only

---

# 9. API Layer Rules

Endpoints MUST include:

### Auth

* `POST /api/v1/auth/login`
* `POST /api/v1/auth/refresh`
* `POST /api/v1/auth/logout`

### Users

* Standard CRUD endpoints

Rules:

* Use dependency injection
* Use response models
* No business logic

---

# 10. Dependency Injection

Provide:

* `get_db`
* `get_user_repository`
* `get_token_repository`
* `get_auth_service`
* `get_user_service`

Use FastAPI `Depends` everywhere.

---

# 11. Environment Configuration

Use Pydantic BaseSettings:

Support:

* dev
* test
* uat
* prod

Each environment MUST:

* Have separate SQLite DB file
* Use `.env` configuration

---

# 12. Migrations

Use Alembic:

* Include setup
* Provide migration example
* Do NOT use `create_all()` in runtime code

---

# 13. Transaction Management

* Transactions controlled in service layer
* Keep transactions short
* Repositories should not commit unless explicitly required

---

# 14. Testing Requirements

Use pytest

Include:

* Auth tests:

  * login
  * refresh
  * logout
* User CRUD tests
* Repository tests

Requirements:

* Separate test DB
* Dependency overrides for DB

---

# 15. Cleanup Strategy (IMPORTANT)

Implement cleanup for expired refresh tokens:

* Function in repository/service:

  * delete expired tokens

* Can be triggered:

  * on startup
  * periodically (simple background task)

---

# 16. Error Handling

* Consistent JSON error responses
* Custom exceptions for:

  * invalid credentials
  * invalid token
  * revoked token

---

# 17. Code Quality Rules

* Full type hints
* No duplicated logic
* Clear naming
* No inline SQL outside repositories
* No business logic in routes

---

# 18. Output Requirements

Generated output MUST:

* Be fully runnable
* Include all files
* Include minimal setup instructions:

  * install deps
  * run migrations
  * start server
* Follow structure exactly

---

# 19. Anti-Patterns (STRICTLY FORBIDDEN)

DO NOT:

* Use async DB access
* Combine schemas and ORM models
* Store access tokens in DB
* Skip refresh token validation
* Put auth logic in routes
* Hardcode secrets
* Share DB across environments

---

# 20. Expected Outcome

The generated system MUST:

* Enforce clean architecture
* Support secure JWT authentication with revocation
* Be testable across environments
* Be production-ready within SQLite constraints

---

If needed, this instruction set can be further tightened to include:

* exact JWT payload schema
* password hashing implementation details
* role-based access control (RBAC)
* example entity with full CRUD and tests


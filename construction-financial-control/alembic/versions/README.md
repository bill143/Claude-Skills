# Migrations

No versions are committed yet — generate the initial migration against your
database:

```bash
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

`alembic/env.py` pulls the connection string from `DATABASE_URL` (via
`app.core.config`) and targets `app.db.base.Base.metadata`, so every model in
`app/models/` is picked up automatically. In development you can skip Alembic
entirely: the API creates tables on startup while `AUTO_CREATE_TABLES=true`.
Set it to `false` in production and run migrations instead.

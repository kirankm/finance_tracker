# SQLite Backup and Restore

Use this path before storing any real financial SMS data.

## Backup

Create a timestamped backup directory on the server:

```bash
mkdir -p backups
```

Run a SQLite backup through the app container:

```bash
docker compose run --rm app python -m app.sqlite_backup backup data/finance_tracker.db backups/finance_tracker-YYYYMMDD-HHMMSS.db
```

For the shared Linode production stack:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.shared-server.yml run --rm app python -m app.sqlite_backup backup data/finance_tracker.db backups/finance_tracker-YYYYMMDD-HHMMSS.db
```

Keep `backups/` off git and copy backups to storage outside this server.

For the first personal pilot, the selected off-server backup approach is a
manual encrypted copy to a local machine controlled by the user after the SQLite
backup command succeeds. Automated cloud backup remains deferred.

## Restore

Stop the app first:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.shared-server.yml down
```

Restore explicitly with `--force`:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.shared-server.yml run --rm app python -m app.sqlite_backup restore backups/finance_tracker-YYYYMMDD-HHMMSS.db data/finance_tracker.db --force
```

Start the app again and verify health:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.shared-server.yml up --build -d
curl https://daily-expense.duckdns.org/health
```

Do not restore over production data unless the selected backup and rollback reason are known.

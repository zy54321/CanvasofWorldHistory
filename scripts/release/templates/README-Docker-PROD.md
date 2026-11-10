# Canvas Docker PROD — unified compose

Since the 2026-11-10 remediation, PROD has exactly **one** compose entry point:

```
E:\01_Work\04_Prod\01_Personal\canvas-history\compose.yaml
```

It defines both services and fixes the project name to `canvas-history`:

| service | container | port | notes |
| --- | --- | --- | --- |
| `db` | `canvas-history-db` | `127.0.0.1:15432` | PostGIS 17-3.6, volume `canvas-history-pgdata` |
| `app` | `canvas-history-prod-app` | `127.0.0.1:5180` | single JAR (web + API), Flyway disabled |

- `deploy/compose.yaml` in this package is the versioned source. `03_发布Prod.bat`
  installs it to the runtime path above and keeps a `compose.yaml.bak-<ts>` copy.
- The data volume is declared `external: true`: compose never creates or deletes
  it, and a missing volume makes `up` fail loudly instead of initialising an
  empty database. Never run `docker compose down -v`.
- The publisher only ever touches `app` (`up -d --no-deps --force-recreate app`).
  If a new package would change the `db` service definition, the script refuses
  unless `-AllowDbRecreate` is passed explicitly after a verified backup.
- Flyway never runs automatically; schema changes are gated by
  `deploy/flyway.sh` and by the Flyway version check in the publisher.

## Environment

- `code/docker-compose.yml` is **not** production anymore: it is the
  `canvas-history-local` sandbox (port 55432, own volume/network) and shares
  nothing with PROD.
- DEV keeps its own file and project: `code/docker-compose.dev.yml`,
  project `canvas-history-dev`, container `canvas-history-db-dev`, port 15433.
- All PROD credentials live only in `<ProdRoot>\config\.env`; every compose
  command must pass `--env-file <ProdRoot>\config\.env`.

## Daily commands

```
# status (read only)
docker compose -f E:\01_Work\04_Prod\01_Personal\canvas-history\compose.yaml ^
               --env-file E:\01_Work\04_Prod\01_Personal\CanvasofWorldHistory\config\.env ps

# logs
docker compose -f ...\canvas-history\compose.yaml --env-file ...\config\.env logs --tail 200 app
```

## Release

Double-click `03_发布Prod.bat`. Preflight verifies the release manifest, JAR hash,
DB name, Flyway version, the protected named volume, the Docker network, and the
unified compose (both `app` and `db` present). A Y/N confirmation is required
before the image build or the service switch.

On failure after cutover the script restores the previous Docker image or the
original Windows JAR; the database schema is never rolled back automatically.

## Limitation

This pipeline supports releases whose database Flyway version matches the
deployed database. A schema upgrade needs the separately approved
forward-migration and backup path first; BAT03 refuses silent migration. This is
a deliberate safety gate, not a completed migration pipeline.

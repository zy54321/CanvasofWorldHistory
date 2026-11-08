# Canvas Docker PROD — controlled transition

This is a **no-database-recreation** transition. Existing `canvas-history-db` and
`canvas-history-pgdata` remain managed by their existing Compose file/project
`canvas-history`; the new app joins the existing `canvas-history-net`.

- Dev: Windows applications + separate `canvas-history-dev` database.
- Prod: Dockerized Java application and existing Dockerized PostGIS database.
- Current PROD URL remains `http://127.0.0.1:5180/`.
- App Compose only touches the `app` service. Never invoke `down -v`.
- Flyway stays disabled in the app; the deployer blocks schema mismatches.
- Do not rename the existing DB Compose project until a separate data-preserving migration is approved.
- Test in DEV using the P1A DEV canary before running production deployment.

## Release BAT03
Double-click `03_发布Prod.bat`. First it performs preflight; a Y/N confirmation
is required before it builds the runtime image or switches service.
It verifies the release manifest, JAR hash, DB name, Flyway version,
existing named production volume, and Docker network.

On failure after cutover it attempts to restore the previous Docker image or
the original Windows JAR; database schema is never rolled back automatically.

## Migration from the existing 1.0.0 release
Existing immutable 1.0.0 archives are not edited. Use the new script from
`scripts/release/templates/publish-container.ps1` with
`-ReleasePackage "E:\01_Work\03_Release\01_Personal\CanvasofWorldHistory\1.0.0"`.
The script uses its own Dockerfile and app-only Compose template.

## Limitation
This initial transition supports releases whose database Flyway version matches
the currently deployed database. A schema upgrade needs the existing separately
approved forward-migration and backup path first; the new BAT03 refuses silent
migration. This is a deliberate safety gate, not a completed migration pipeline.

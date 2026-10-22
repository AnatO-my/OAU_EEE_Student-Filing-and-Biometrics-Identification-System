# PostgreSQL backup and restore verification

The backup and restore procedure has been exercised against both synthetic PostgreSQL 18.6 data and the actual Aiven integration database. On 21 October 2026, the user confirmed a successful Aiven backup and isolated local restoration of **41 application tables**, with matching row hashes, constraints and sequences. The Aiven password remained private in the user's terminal.

## Back up the Aiven integration database

Stop local application writers and workers briefly before the drill. PostgreSQL's shared snapshot gives consistent table contents; sequence increments are not transactional, so exact sequence-state comparison also requires writers to remain quiet while the backup is taken.

In the PowerShell terminal already configured for Aiven:

```powershell
. .\private-data\aiven\configure.ps1 -UseExistingPassword
.\scripts\backup-postgres.ps1 -VerifyRestore
```

The single command chooses a new timestamped filename and verifies its restore.
For an explicit filename, the equivalent two commands are:

```powershell
.\scripts\backup-postgres.ps1 -OutputPath .\backups\aiven-integration-20261021.dump
.\scripts\restore-postgres-test.ps1 -Archive .\backups\aiven-integration-20261021.dump
```

Use a new output filename for each backup. If this is a new terminal, run the private configuration profile without `-UseExistingPassword` and enter the password at its hidden prompt. Keep the password out of command arguments and chat.

Success creates the custom-format `.dump` archive and its `.dump.json` verification manifest. The manifest contains source host/database metadata, table row counts and digests, constraint definitions, sequence state and the archive SHA-256 digest; it contains no database password or application rows. The password is passed to the short-lived utility process through its environment and is not saved in a password file. Provider failure text is suppressed.

The helper uses certificate and hostname verification (`verify-full`) for hosted backups and refuses weaker modes. It disables connection-service/password-file discovery and inherited host-address overrides. Two database connections are used during the exported-snapshot dump; allow for these within the Aiven service's 20-connection limit.

## What restore verification does

`restore-postgres-test.ps1` starts a new local PostgreSQL cluster on a random loopback port. It checks the archive digest, creates a new random `eee_restore_verify_*` database, restores in a single transaction and compares all user tables' row counts/content digests, constraint definitions and sequence state against the manifest. It then drops only that newly created database, stops the cluster and removes its newly created cluster directory on success.

There is no target database-name argument and no `--clean` or `--create` archive option. It cannot reconnect to an Aiven database by an embedded archive database name. The verification path refuses remote target addresses. Existing `defaultdb`, application databases and other local clusters are not restore targets. Failed runs retain their own cluster logs for diagnosis after stopping the server.

The scripts never restore over the live database. Promoting a verified restored database to become the application's live database is a separate operational change, with new connection settings and an application smoke test.

## Client setup

These binary assets are already prepared in this workspace. To reproduce them on another Windows x64 checkout:

```powershell
.\.venv\Scripts\python.exe scripts\install-postgres-client.py
.\.venv\Scripts\python.exe tools\prepare_postgres_runtime.py --aiven-client
```

The runtime lives in ignored `private-data/postgres18/`. The Aiven backup client lives separately in `private-data/postgres18-aiven-client/bin/`: `pg_dump` and `pg_restore` 18.6 with the tested official libpq 16.15 TLS transport. A current server-major dump utility is required for an 18.x source; the 16.x `pg_dump` executable must not be used against Aiven 18.x. The publisher's server DLL set remains intact.

The compatible combination has passed a full synthetic dump/restore and actual endpoint TLS-positive/hostname-negative checks. The user's subsequent authenticated Aiven backup and successful 41-table local restore also validated the current service's permissions and application objects.

## Backup scope and handling

This is a portable logical application-database backup. Owner/ACL statements are omitted for restoration into a new environment. Cluster-wide roles, provider configuration, environment secrets, CA files and uploaded filesystem media are separate recovery inputs. Archive contents include database application data, including authentication password hashes and any stored attendance templates; treat the archive as sensitive. `backups/`, `private-data/` and `tmp/` are ignored by Git but are not automatically encrypted. Keep completed archives in encrypted storage and copy them to a separate protected location; the scripts do not create off-device copies or schedule retention.

The restore comparison explicitly checks tables, rows, constraints and sequences. `pg_restore --exit-on-error --single-transaction` also requires the complete schema restoration to succeed. It is not a binary-identical catalog comparison, provider-level point-in-time recovery or a backup of external files.

For a repeatable synthetic drill without live credentials:

```powershell
.\.venv\Scripts\python.exe tools\run_attendance_postgres_tests.py --pg-bin private-data\postgres18\bin --skip-tests --backup-drill --keep-cluster --backup-client-bin private-data\postgres18-aiven-client\bin
.\.venv\Scripts\python.exe tools\test_postgres_backup.py
```

Observed on 21 October 2026: 43 tables, 393 constraints and 33 sequences restored with matching data, foreign keys and identity values; a corrupted archive was rejected. See [the validation checkpoint](postgres-validation-checkpoint.md) for test evidence and limitations. PostgreSQL documents the [custom-format dump and snapshot options](https://www.postgresql.org/docs/18/app-pgdump.html) and [transactional restore behavior](https://www.postgresql.org/docs/18/app-pgrestore.html).

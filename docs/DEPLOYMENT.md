# Deploying the student demo

This guide takes the project from a laptop to an HTTPS address. **Nothing here has been provisioned yet.** Choosing a host, creating accounts and anything that costs money are decisions for the project owner.

## 1. Choosing a host

Checked in October 2026 from provider pages and third-party trackers. Free tiers change often, so confirm each one on the provider's pricing page before signing up.

| Option | Cost | Sleeps? | MySQL | Backups | Limitations |
|---|---|---|---|---|---|
| **A. Your laptop, local network only** (current setup) | Free | Only when the laptop is off | Your local MySQL 8 | `mysqldump` (section 7) | Not reachable from outside; fine for the in-person review |
| **B. Render free web service + Aiven free MySQL** | $0 | Web service sleeps after 15 min idle; the first request then takes about a minute | Aiven free: 1 node, 1 GB RAM, **1 GB disk**, one per organisation; **may be powered off when unused** (you get a notice and can power it back on) | Aiven includes backups; also run `mysqldump` yourself | Slow first load; database can be switched off; no SLA |
| **C. Render Starter + Aiven Developer** | About $7 + $5 per month | No | Aiven Developer: dedicated VM, larger disk, not powered off | Aiven backups + `mysqldump` | Paid; the smallest always-on setup with these two providers |
| **D. Railway Hobby** | $5/month of usage credit (pay above it); short trial credit | No | Run a MySQL service in the same project | Volume snapshots depend on plan; run `mysqldump` | Usage-based billing: watch the dashboard; trial terms vary |
| **E. PythonAnywhere** | Free tier / paid from about $10 per month | Free web apps expire after one month unless renewed | **Free accounts created after mid-January 2026 have no MySQL**; paid plans include it | Paid plans | Free tier unsuitable for this project now |

**Recommendation.**
- **For the review on 26 October**, use **A**. It is free and already working, and it doesn't need the internet.
- **If examiners must open it remotely**, use **B**. It costs nothing, but you should open the site a minute before the demo so the web service wakes up. Also check that the Aiven database is powered on.
- **For anything longer-lived**, use **C** or **D**.

Before choosing B or C, confirm that the provider allows `CREATE PROCEDURE` and CHECK constraints (MySQL 8.0.16+) by running `sql/01`–`13` against a trial database.

Sources: [Render pricing](https://render.com/pricing), [Render free tier notes](https://livemy.app/blog/render-pricing), [Aiven MySQL free tier](https://aiven.io/docs/products/mysql/concepts/mysql-free-tier), [Aiven free plan](https://aiven.io/docs/platform/concepts/free-plan), [Railway pricing](https://railway.com/pricing), [PythonAnywhere free accounts](https://help.pythonanywhere.com/pages/FreeAccountsFeatures/).

## 2. Database accounts (once)

Copy `sql/14_db_accounts.sql.example` to a folder **outside** the repository. Replace the three `CHANGE_ME_*` values with long random passwords, run it once as a MySQL administrator, then delete the copy:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(24))"     # run 3 times, one per account
cp sql/14_db_accounts.sql.example ~/db_accounts.sql && nano ~/db_accounts.sql
sudo mysql < ~/db_accounts.sql && shred -u ~/db_accounts.sql
```

| Account | Used by | Rights |
|---|---|---|
| `smartlab_app` | the running app (`DB_USER`) | rows only: SELECT/INSERT/UPDATE/DELETE + EXECUTE procedures |
| `smartlab_admin` | you: migrations, backups, `create-user` | everything on `smart_lab_equipment_db` only |
| `smartlab_test` | automated tests | the two test databases only |

On a hosted MySQL, the provider's admin user plays the role of root. Change `'localhost'` in the file to the host the app connects from, if the provider requires it.

## 3. Schema and migrations

**New database.** Run these as `smartlab_admin`:
```bash
for f in 01_create_database 02_create_tables 03_insert_sample_data 08_create_views \
         11_transaction_procedures 12_maintenance_procedures 13_app_users 15_student_portal; do
  mysql -u smartlab_admin -p < sql/$f.sql
done
```
Skip `03_insert_sample_data.sql` if you want an empty inventory instead of the demo data.

**Existing database (keep its data).** Run only the additive migration:
```bash
mysqldump -u smartlab_admin -p --single-transaction --routines --no-tablespaces smart_lab_equipment_db > backup-before-13.sql
mysql -u smartlab_admin -p < sql/13_app_users.sql            # safe to re-run; never drops or changes data
mysql -u smartlab_admin -p < sql/15_student_portal.sql       # student accounts + requests; also additive
```
For a database built before the register-number check, also run the `ALTER TABLE` command from README section 5.

**Never** run `sql/10_reset_database.sql` on a database you want to keep. It drops everything.

## 4. First administrator

There is no default account. On the server (or any machine that can reach the database), with the production environment variables set and `DB_USER=smartlab_admin`:

```bash
flask --app wsgi create-user --username your.name --role admin
# prompts for the password twice; nothing is echoed or logged
```

Then sign in, open **Users**, and create one account per person with the least role they need (docs/SECURITY.md section 2).

**Student accounts.** On **Users → Student sign-in**, open activation for the students who should use the site. They have 14 days to activate at `https://<your-site>/activate` with their register number and the e-mail on record. Tell them the address yourself; the app sends no e-mail. Read the self-activation risk in docs/SECURITY.md section 6 before opening activation on a public site.

## 5. Environment variables (set in the host's dashboard)

| Variable | Value |
|---|---|
| `APP_ENV` | `production` |
| `SECRET_KEY` | 64 random hex characters: `python3 -c "import secrets; print(secrets.token_hex(32))"`. Keep it stable: changing it signs everyone out |
| `DB_HOST`, `DB_PORT`, `DB_NAME` | from the database provider |
| `DB_USER` / `DB_PASSWORD` | `smartlab_app` and its password |
| `DB_SSL_CA` | path to the provider's CA certificate if it requires TLS (Aiven does) |
| `TRUST_PROXY` | `1` on Render/Railway (one HTTPS proxy in front); `0` when nothing is in front |
| `WEB_CONCURRENCY`, `GUNICORN_THREADS` | optional; default 2 × 4 (max 8 database connections) |
| `APP_REFERENCE_DATE` | `2026-10-10` only for the sample-data demo; remove for real use |

The app refuses to start if a required value is missing or unsafe. The host's log shows which setting it was, never the value.

## 6. Start command and health check

```bash
pip install -r requirements.txt
gunicorn --config gunicorn.conf.py wsgi:app
```

- **Health check path:** `/healthz`. It returns `200 {"status":"ok"}` when the database answers, and `503 {"status":"unavailable"}` otherwise. It is public and reveals nothing else.
- **gunicorn settings** (`gunicorn.conf.py`):
  - 30 s request timeout.
  - Workers are recycled every ~1000 requests.
  - Request line and header size limits.
  - Logs go to stdout, without query strings.
  - `preload_app` makes a configuration error stop the start-up instead of failing on the first request.
- **HTTPS:** the platform terminates TLS. With `TRUST_PROXY=1` the app sees `https`, sends HSTS, and the session cookie is `Secure`.

## 7. Backups and restore (tested)

**Backup.** Run as `smartlab_admin`, daily and before any migration. Keep copies off the server:
```bash
mysqldump -u smartlab_admin -p --single-transaction --routines --triggers --no-tablespaces \
  --set-gtid-purged=OFF smart_lab_equipment_db | gzip > smartlab-$(date +%F).sql.gz
```

`--routines` saves the four stored procedures. The admin account needs `SHOW_ROUTINE` for this (it's in the accounts file). Without it the dump fails with "insufficient privileges to SHOW CREATE PROCEDURE", and the backup has no procedures.

The backup contains student names and e-mail addresses and password hashes, so store it like the database itself: private, encrypted at rest, and deleted when no longer needed.

**Restore.** Restore into a new, empty database first, check it, and only then point the app at it:
```bash
mysql -u <admin> -p -e "CREATE DATABASE smartlab_restore CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"
gunzip -c smartlab-YYYY-MM-DD.sql.gz | mysql -u <admin> -p smartlab_restore
mysql -u <admin> -p smartlab_restore -e "SELECT COUNT(*) FROM student; SELECT COUNT(*) FROM equipment;
  SELECT ROUTINE_NAME FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA = 'smartlab_restore';"
```

**What was tested.** A test database was backed up with the `smartlab_admin` account and restored into a scratch database, then checked:
- row counts were identical for every table;
- `CHECKSUM TABLE` matched for student, equipment, allocation, return, maintenance and app_user;
- all 4 procedures, 4 views and 22 CHECK constraints were present;
- a procedure call worked on the restored copy.

The first attempt failed because the admin account lacked `SHOW_ROUTINE` (the backup had no procedures). That is why the grant is in the accounts file. Details are in docs/TEST_REPORT.md.

## 8. Before the demo (checklist)

- [ ] `APP_ENV=production`, a fresh `SECRET_KEY`, `DB_USER=smartlab_app`; nothing uses root
- [ ] `/healthz` returns 200 over HTTPS
- [ ] Signing in over `http://` redirects or is refused by the host (HTTPS only)
- [ ] One admin account plus one account per role used in the demo; no shared passwords
- [ ] A backup taken and a test restore done
- [ ] Free tier: open the site and the database console about a minute before presenting (cold start)

## 9. Undoing the deployment changes

Everything added for deployment is additive:
- The tables from `15_student_portal.sql` and `13_app_users.sql` can be dropped, in that order, without touching the inventory data:
  - `DROP TABLE equipment_request, student_account;`
  - `DROP TABLE login_attempt, app_user;`

  This loses the requests and accounts, and nobody can sign in until the migrations are run again.
- The database accounts can be removed with `DROP USER`.

No existing table, column or row was changed.

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

Step-by-step instructions for option B are in section 10. Before choosing B or C, confirm that the provider allows `CREATE PROCEDURE` and CHECK constraints (MySQL 8.0.16+) by running `sql/01`–`13` against a trial database.

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

## 10. Step by step: Render (free) + Aiven MySQL (free)

This is option B from section 1. It costs nothing, but the site sleeps after 15 minutes without visitors (the first page then takes about a minute), and Aiven may power off a free database that is not used. Open the site a few minutes before a demo.

You need a GitHub account (this repository), an Aiven account and a Render account. Both providers offer sign-in with GitHub or e-mail; neither free plan should ask for a card. If one does, stop: that is a paid plan.

### 10.1 Create the database (Aiven)

1. Sign in at <https://console.aiven.io>, choose **Create service → MySQL → Free plan**, pick a region close to you (and to the Render region you will choose) and name it `smartlab-db`.
2. Wait until the service shows **Running**. On its **Overview** page note the **Host**, **Port**, **User** (`avnadmin`) and **Password**, and click **Download CA certificate**. Save the file as `~/aiven-ca.pem`.
3. On your laptop, put the connection details in a private file instead of typing the password on the command line:

   ```bash
   nano ~/.aiven.cnf
   ```
   ```ini
   [client]
   host=YOUR-HOST.aivencloud.com
   port=YOUR-PORT
   user=avnadmin
   password=YOUR-AVNADMIN-PASSWORD
   ssl-mode=VERIFY_IDENTITY
   ssl-ca=/home/YOUR-LINUX-USER/aiven-ca.pem
   ```
   ```bash
   chmod 600 ~/.aiven.cnf
   mysql --defaults-extra-file=~/.aiven.cnf -e "SELECT VERSION();"     # should print 8.0.x
   ```

### 10.2 Build the schema and load the data

```bash
cd ~/smart-lab-equipment-management.
git pull
for f in 01_create_database 02_create_tables 03_insert_sample_data 08_create_views \
         11_transaction_procedures 12_maintenance_procedures 13_app_users 15_student_portal; do
  echo "== $f"; mysql --defaults-extra-file=~/.aiven.cnf < sql/$f.sql || break
done
```

Leave out `03_insert_sample_data` for an empty inventory. Aiven enforces `sql_require_primary_key`; every table in this project has a primary key, so no change is needed.

### 10.3 Create the runtime account

The website must not use `avnadmin`. Generate a password, then create a least-privilege account (same rights as `smartlab_app` in section 2, but allowed from any host, because Render's address is not fixed):

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(24))"     # copy the output
mysql --defaults-extra-file=~/.aiven.cnf
```
```sql
CREATE USER 'smartlab_app'@'%' IDENTIFIED BY 'PASTE-THE-GENERATED-PASSWORD';
GRANT SELECT, INSERT, UPDATE, DELETE, EXECUTE ON smart_lab_equipment_db.* TO 'smartlab_app'@'%';
ALTER USER 'smartlab_app'@'%' WITH MAX_USER_CONNECTIONS 20;
EXIT;
```

Keep this password for step 10.5. It is typed into the MySQL prompt, so it does not end up in your shell history.

### 10.4 Create the sign-in accounts in the online database

`flask seed-accounts` creates the ready-made accounts and generates a password for each one:

| Who | Sign-in name | Role |
|---|---|---|
| Darshan S, Abishek Raj, Chaitanya Kumar | `darshan.s`, `abishek.raj`, `chaitanya.kumar` | Administrator |
| Kavitha Ramesh, Priya Sundaram, Ramesh Kumar (lab teachers, linked to their lab staff records) | `kavitha.ramesh`, `priya.sundaram`, `ramesh.kumar` | Lab manager |
| Every student in the `student` table (10 in the sample data) | their register number, e.g. `24BCE1012` | Student (ready to use, no activation needed) |

The passwords are written only to `~/smartlab-credentials.csv` on your laptop (readable by you alone). They are not shown on screen, not logged and not stored in the repository; the database keeps only scrypt hashes. Run the command on your laptop, pointed at Aiven. Environment variables override `.env`, so your local settings are untouched:

```bash
source .venv/bin/activate
read -rp  "Aiven host: " DB_HOST; read -rp "Aiven port: " DB_PORT
read -rsp "avnadmin password: " DB_PASSWORD; echo
DB_HOST=$DB_HOST DB_PORT=$DB_PORT DB_USER=avnadmin DB_PASSWORD=$DB_PASSWORD \
DB_SSL_CA=$HOME/aiven-ca.pem flask --app run seed-accounts
unset DB_HOST DB_PORT DB_PASSWORD
column -s, -t ~/smartlab-credentials.csv      # view the list
```

Give each person only their own line, then move the file somewhere safe or delete it. Everyone can change their password after signing in (**Change password** in the user menu). Running the command again leaves existing accounts unchanged; `--reset` gives all of them new passwords (written to a new file named with `--out`) and signs them out. `create-user` still works for any extra account.

The same command works on your local database: run `flask --app run seed-accounts` without the `DB_…` variables.

### 10.5 Create the website (Render)

1. Sign in at <https://dashboard.render.com> with GitHub and allow Render to read this repository.
2. Choose **New → Blueprint**, select this repository and the `main` branch. Render reads `render.yaml` and asks for four values:
   - `DB_HOST` and `DB_PORT`: from Aiven
   - `DB_USER`: `smartlab_app`
   - `DB_PASSWORD`: the password from step 10.3
3. Open the new service **smart-lab-equipment → Environment → Secret Files**, add a file named `aiven-ca.pem` and paste the contents of `~/aiven-ca.pem` (`cat ~/aiven-ca.pem`). Render places it at `/etc/secrets/aiven-ca.pem`, which is what `DB_SSL_CA` points to.
4. Click **Manual Deploy → Deploy latest commit**. The first deploy may fail before the Secret File exists; that is expected.
5. When the log shows gunicorn listening, open `https://<your-service>.onrender.com/healthz`. It should show `{"status":"ok"}`. Then open the site and sign in with the account from step 10.4.

### 10.6 If something goes wrong

| Symptom (Render log or page) | Cause and fix |
|---|---|
| `Refusing to start in production: …` | A setting is missing; the message names it. Check **Environment** |
| `/healthz` shows `{"status":"unavailable"}` | The app cannot reach MySQL: wrong host, port, user or password; the Secret File is missing; or the Aiven service is powered off (power it on in the Aiven console) |
| Build fails on the Python version | Change `.python-version` to an exact version Render lists, e.g. `3.13.5` |
| First page takes about a minute | Normal on the free plan after 15 minutes idle |

### 10.7 Keeping it safe

- Never paste `avnadmin` or `smartlab_app` passwords into chat, code or GitHub. `~/.aiven.cnf` stays on your laptop (`chmod 600`).
- The sample data is fictional, so a public demo exposes no real person. Before entering real student data, read docs/SECURITY.md and remove `APP_REFERENCE_DATE`.
- Do not open student self-activation (**Users → Student sign-in**) on the public site unless you need it for the demo; see the self-activation risk in docs/SECURITY.md section 6.
- Back up before changing anything: `mysqldump --defaults-extra-file=~/.aiven.cnf --single-transaction --routines --set-gtid-purged=OFF smart_lab_equipment_db > backup.sql`.

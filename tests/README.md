# Tests

The project has three automated test suites, 257 tests in all, each run by one command. Every suite builds its **own** database from the SQL scripts, so none of them reads or changes `smart_lab_equipment_db`. `tests/web/conftest.py` refuses to run unless its target is the dedicated `…_apptest` database (TA74). The suites can also run under the restricted `smartlab_test` MySQL account, which has rights on the two test databases only (`sql/14_db_accounts.sql.example`).

The application tests sign in with fake accounts created inside the test database (one per role) and a fixed test-only password; the browser walkthrough generates random throw-away passwords on every run. No real credentials are used.

| Suite | IDs | Command | Database it builds | Needs |
|---|---|---|---|---|
| Database | TC01–TC83 | `bash tests/run_tests.sh` | `smart_lab_equipment_test` | bash, `mysql` client |
| Web application | TA01–TA32, TA40–TA48, TA50–TA74, TA80–TA96 (155 tests) | `python -m pytest` | `smart_lab_equipment_apptest` (rebuilt before every test) | `pip install -r requirements.txt`, `mysql` client |
| Browser walkthrough | TB00–TB18 | `python tests/browser_walkthrough.py` | `smart_lab_equipment_apptest` | `pip install playwright` and `python -m playwright install chromium` |

| File | Content |
|---|---|
| `test_cases.md` | Every test case: objective, steps, expected result |
| `run_tests.sh` | Database suite runner (prints PASS/FAIL per test) |
| `web/` | pytest suite: `conftest.py` (fixtures), page/search, CRUD, workflow, reports/security/validator tests |
| `browser_walkthrough.py` | Drives Chromium through 10 user journeys; saves screenshots to `docs/screenshots/` |
| `../docs/TEST_REPORT.md` | Results of the latest runs |

## Connecting to MySQL

- **Database suite.** It uses the plain `mysql` command. That command reads `~/.my.cnf`, or uses socket login for the current OS user. To use a saved login instead:
  ```bash
  mysql_config_editor set --login-path=smartlab --host=localhost --user=root --password
  MYSQL_CMD="mysql --login-path=smartlab" bash tests/run_tests.sh
  ```
- **Application suite and browser walkthrough.** These read the same variables as the app: `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, and optionally `DB_UNIX_SOCKET`. For example:
  ```bash
  DB_USER=labadmin DB_PASSWORD='...' python -m pytest
  ```
  The password is passed to the `mysql` client through a temporary option file, never on its command line.

The MySQL account needs permission to create and drop the two test databases:

```sql
GRANT ALL PRIVILEGES ON smart_lab_equipment_test.*    TO 'labadmin'@'localhost';
GRANT ALL PRIVILEGES ON smart_lab_equipment_apptest.* TO 'labadmin'@'localhost';
```

## Notes

- **Run times.** The database suite takes about 6 seconds, the application suite about 1–2 minutes (it rebuilds the database 155 times), and the browser walkthrough about 30 seconds.
- **Keeping the test database.** Set `KEEP_TEST_DB=1` to keep `smart_lab_equipment_test` after the database suite.
- **Browser path.** The walkthrough uses Playwright's own Chromium. `CHROMIUM_PATH=/path/to/chrome` points it at another browser.

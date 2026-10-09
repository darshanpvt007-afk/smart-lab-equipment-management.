# Tests

| File | Content |
|---|---|
| `test_cases.md` | Definitions of the 63 test cases (TC01–TC63), with SQL you can run by hand |
| `run_tests.sh` | Runs every test case automatically and prints PASS/FAIL |
| `../docs/TEST_REPORT.md` | Results of the latest run |

## Running the automated tests

Requirements:
- MySQL 8.0.16 or later, with the server running
- a MySQL account that may create and drop a database named `smart_lab_equipment_test`
- `bash` (Linux, macOS, WSL or Git Bash on Windows)

```bash
# from the project root
bash tests/run_tests.sh
```

By default the script uses the plain `mysql` command, which reads `~/.my.cnf` or uses the socket login of the current OS user. If your account needs a password, store it once in an encrypted login path rather than typing it on the command line:

```bash
mysql_config_editor set --login-path=smartlab --host=localhost --user=root --password
MYSQL_CMD="mysql --login-path=smartlab" bash tests/run_tests.sh
```

To keep the test database for inspection afterwards:

```bash
KEEP_TEST_DB=1 bash tests/run_tests.sh
```

## What the runner does

1. Makes copies of the SQL files with `smart_lab_equipment_db` replaced by `smart_lab_equipment_test`. **Your development database is never read or changed.**
2. Drops and rebuilds `smart_lab_equipment_test` from scripts 01, 02, 03, 08 and 11.
3. Runs the schema, constraint, query-result, validation, transaction, concurrency and history tests.
4. Runs the reset script against the test database, rebuilds it, and validates it again.
5. Drops the test database (unless `KEEP_TEST_DB=1`) and prints `Passed / Failed / Total`. The exit status is 0 only if every test passed.

The concurrency tests (TC53, TC54) open parallel `mysql` sessions and use `SLEEP(2)`, so a full run takes about 5–10 seconds.

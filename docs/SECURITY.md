# Security model

How the web application protects the inventory data. Every control listed here is checked by an automated test (IDs in brackets; definitions in `tests/test_cases.md`).

## 1. Accounts and sign-in

- **No default accounts.** Migration `sql/13_app_users.sql` creates the `app_user` table empty. The first administrator is created on the server with `flask --app wsgi create-user` (docs/DEPLOYMENT.md, step 4), which asks for the password twice and never echoes or logs it (TA70).
- **Password storage.** Only a salted scrypt hash from `werkzeug.security` is stored (`app_user.password_hash`); the password itself is never stored, logged or shown. Two accounts with the same password get different hashes (TA68).
- **Password rules.** 12–128 characters, not containing the username, at least 5 different characters (TA68). The 128-character maximum bounds the hashing work an attacker can force per request.
- **Sign-in.** A wrong password and an unknown username give the same message, status and (approximately) the same response time, so the page does not reveal which accounts exist (TA51).
- **Brute-force defence.** Failed sign-ins are recorded in `login_attempt`. After 5 failures for one username, or 20 from one client address, within 15 minutes, further attempts are refused with HTTP 429, even with the right password (TA64, TA65). A successful sign-in restarts that username's count. Rows older than one day are deleted automatically (TA66), so the table is not a long-term log of who tried to sign in.
- **Accounts are deactivated, never deleted**, so who could do what stays readable. Administrators cannot change their own role or deactivate themselves, and the last active administrator cannot be removed (TA69).

## 2. Roles and permissions

The server checks the role on **every request**. `app/auth.py` maps each of the 61 routes to one permission; a route that is not in the map is refused for everyone (fail closed, TA58), and a test checks that every route is in the map (TA55). Buttons a role cannot use are hidden (TA59), but hiding is only a convenience: the server refuses the request either way (TA56, TA57).

| Permission | What it allows | Admin | Lab manager | Inventory staff | Technician |
|---|---|:-:|:-:|:-:|:-:|
| view | Dashboard, all lists and detail pages, search, reports, CSV export | ✓ | ✓ | ✓ | ✓ |
| issue_return | Issue equipment to students, record returns | ✓ | ✓ | ✓ | |
| maintain | Schedule, start and complete maintenance | ✓ | ✓ | | ✓ |
| edit_equipment | Add and edit equipment | ✓ | ✓ | ✓ | |
| edit_students | Add and edit students | ✓ | ✓ | ✓ | |
| manage_reference | Labs, categories, suppliers, purchases, lab staff | ✓ | ✓ | | |
| delete_records | Delete any record (the database still refuses deletes that would lose history) | ✓ | ✓ | | |
| issue_return also covers | Approving or rejecting student requests (`/requests/`) | ✓ | ✓ | ✓ | |
| manage_users | Create accounts, change roles, deactivate, reset passwords; open, reset or deactivate student sign-in | ✓ | | | |

Every signed-in user can change their own password and sign out.

## 3. Sessions and requests

| Control | Detail | Test |
|---|---|---|
| Session renewal | The session is cleared and a new CSRF token issued at sign-in; cleared again at sign-out | TA50, TA52 |
| Sign-out | POST only, with CSRF token | TA52 |
| Forced sign-out | Changing or resetting a password, changing a role or deactivating an account increments `session_epoch`; older sessions are signed out on their next request | TA61, TA62 |
| Session lifetime | 8 hours (`SESSION_HOURS`) | TA63 |
| Cookie flags | `HttpOnly`, `SameSite=Lax`; `Secure` (HTTPS only) in production | TA50, TA63 |
| CSRF | Every POST, including sign-in, must carry the session's token (constant-time comparison) | TA54, TA60 |
| Open redirects | After sign-in, only paths on this site are followed; `//host`, `https://…`, `/\host` and `javascript:` go to the dashboard | TA67 |
| SQL injection | All SQL uses `%s` parameters; sort keys and filters come from fixed whitelists | TA06, TA41 |
| Cross-site scripting | Jinja escapes every value; Content-Security-Policy allows only this site's scripts and forbids inline scripts and event handlers | TA31, TA72 |
| Clickjacking | `X-Frame-Options: DENY`, `frame-ancestors 'none'` | TA72 |
| Other headers | `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`, `Strict-Transport-Security` in production; `Cache-Control: no-store` on signed-in pages (shared lab PCs) | TA72 |
| Request size | Bodies over 64 KB are refused (413) | TA72 |
| Error pages | Fixed messages only: no exception text, SQL, hostnames or settings | TA72 |
| CSV export | Cells starting with `= + - @` are prefixed with `'` (spreadsheet formula injection) | TA44 |

## 4. Secrets and configuration

- Secrets come only from environment variables (or the host's secret manager). `.env` is for local development, is git-ignored, and is not read by `wsgi.py`. `.env.example` holds placeholders only.
- With `APP_ENV=production` the app **refuses to start** unless `SECRET_KEY` is at least 32 characters, `DB_USER` is set and is not `root`, `DB_PASSWORD` is set, HTTPS-only cookies are on and testing mode is off. The error names the setting, never its value (TA71).
- Logs never contain passwords, password hashes, session cookies, CSRF tokens, database passwords or `SECRET_KEY`. The gunicorn access log omits query strings, so search text is not logged. Checked by searching the server log for each secret after a production-mode run (docs/TEST_REPORT.md).

## 5. Database

- **Three MySQL accounts** (`sql/14_db_accounts.sql.example`):
  - **`smartlab_app`** is used by the running app. It can SELECT, INSERT, UPDATE, DELETE and EXECUTE on the project database only. It cannot create, alter, drop or truncate anything, read other databases, or grant itself rights. All of these were verified.
  - **`smartlab_admin`** runs migrations and backups on the project database only.
  - **`smartlab_test`** is for the automated tests and has rights on the two test databases only.
- **Stored procedures** run with their definer's rights, so the runtime account only needs EXECUTE and cannot change them.
- **Connections.** One per request. It is rolled back and closed at the end of every request, and has a 5-second connect timeout. Optional TLS with certificate verification (`DB_SSL_CA`) for hosted MySQL.
- **Migrations are additive.** `13_app_users.sql` only creates tables if they do not exist. A test runs it twice on a database with data and checks that every row is still there (TC76–TC77, TA73). `10_reset_database.sql` is never run by the app or by deployment steps.

## 6. Student accounts (`sql/15_student_portal.sql`)

Students are **not** a staff role and hold none of the permissions above. They have a separate account table (`student_account`), sign in with their register number, and can open only three pages under `/my/`.

| Control | Detail | Test |
|---|---|---|
| Own data only | Every portal query is filtered by the student id stored in the signed-in session, never by an id from the URL or form. A student sees their own loans, requests and history, plus a read-only list of available items; no other student's name, register number or e-mail appears | TA83, TA86 |
| No staff pages | Every staff route returns 403 for a student; `/` redirects to `/my/` | TA84, TB18 |
| No staff on student pages | Staff accounts get 403 on `/my/` | TA56 |
| Requests | At most 3 open requests per student; start no earlier than today and no more than 30 days ahead; 14-day maximum; purpose required; one pending request per item (database UNIQUE index) | TA85, TC82 |
| Approval | Only roles with `issue_return`. Approving calls `sp_allocate_equipment` (same checks as the Issue form); if the item is no longer available the request stays pending with the procedure's message | TA87, TA88 |
| Sign-in | Same throttling, session renewal and password rules as staff. Staff usernames may not look like a register number, so the two kinds of account can never collide | TA82, TA90, TA91 |

**Self-activation.**
- An administrator opens activation, for every student without an account or for one student, on **Users → Student sign-in**.
- Within 14 days the student enters their register number, the e-mail on record and a new password at `/activate` (TA80).
- Activation works once.
- One message covers every failure (wrong e-mail, not opened, expired, deactivated or unknown student), so the page does not reveal which accounts exist (TA81).
- Attempts are throttled like sign-in.

**Known risk of self-activation.** A register number and an e-mail address are not secret. Someone who knows both could activate another student's account before they do. This is limited by:
- the 14-day window, opened only when an administrator chooses;
- one-time activation;
- throttling.

The student notices at once, because their own activation fails. An administrator can then **Reset** the account: the password is cleared, every session is ended and activation reopens (TA89). For a real deployment, send each student a one-time activation link by e-mail instead (not implemented: the app sends no e-mail).

## 7. Known limitations

- No multi-factor authentication and no self-service password reset: an administrator resets forgotten passwords.
- The address-based throttle trusts `X-Forwarded-For` only when `TRUST_PROXY` is set; behind a proxy that is not configured correctly, all users could share one address and hit the per-address limit together.
- Sessions are signed cookies (Flask's default). Signing out ends the session in that browser, and `session_epoch` ends all sessions of an account. A copied cookie stays valid until the epoch changes or it expires (8 hours).
- No audit trail of who changed which record; `app_user.last_login_at` and the 1-day `login_attempt` table are the only activity records.

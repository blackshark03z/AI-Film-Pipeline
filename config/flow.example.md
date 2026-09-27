# Local Flow configuration

Set `FLOW_COOKIE_PATH` and `FLOW_SESSION_PATH` to existing local files outside Git.
Optional `FLOW_PROJECT_ID` must match the session binding. Use ignored `secrets/`
storage or paths outside this repository. Never commit browser storage or cookies.

Session metadata uses `schema: google-flow-session-v1` with `project_id` and an
optional matching `project_url`. No account/tier is inferred from a local cookie.

Install the optional transport with `pip install -e ".[flow]"` and provision its
Chromium browser with `python -m patchright install chromium` before read-only
preflight. These setup steps do not acquire credentials. Missing runtime reports
UNAVAILABLE. No login, refresh, CAPTCHA handling,
project modification or generation is performed. Unit tests use fake transport state.

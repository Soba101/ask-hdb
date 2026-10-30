# Repository security

Settings on github.com/Soba101/ask-hdb, set on 2026-10-31.

| Setting | Value |
|---|---|
| `main` | Pull request required, stale approvals dismissed, linear history, no force push, no deletion |
| `gh-pages` | No force push, no deletion (the demo is pushed directly) |
| Merge method | Squash only; merged branches are deleted |
| Secret scanning and push protection | On |
| Dependabot alerts and security updates | On |

Notes:
- No approval count is required. The repo has one owner, who can still merge their own pull requests.
- Admin bypass stays on for the owner, so a rule cannot lock the owner out.
- No required CI checks exist yet, because the repo has no workflow. Add the checks here when a workflow exists.
- Secrets live in `.env` (git-ignored). The app has no login: keep the rate limits and the daily token cap on when it is public.

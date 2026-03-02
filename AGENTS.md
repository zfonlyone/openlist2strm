# AGENTS

## Security Baseline
- Never create, modify, or commit any secret file inside this repository.
- Never write real credentials into source files, examples, scripts, compose files, or docs.
- Treat all tokens, passwords, API keys, private keys, and session strings as prohibited content.

## Prohibited In-Repo Files
- `.env`, `.env.*`
- `*.pem`, `*.key`, `id_rsa`, `id_ed25519`, `authorized_keys`
- Any runtime credential dump file (for example: `secrets.txt`, `token.txt`, `session.json`).

## Prohibited Actions For AI
- Do not run commands that print secret values (for example: `env`, `printenv`, `cat` on secret files).
- Do not add fallback defaults that look like real tokens/passwords.
- Do not auto-generate or inject credentials during code changes.

## Allowed Secret Handling
- Use placeholders only (for example: `your-token-here`, `example.com`).
- Keep runtime secrets outside the repo (system env, secret manager, or `/etc/...` path).
- For CI/CD, use platform secret storage only (GitHub Actions Secrets, etc.).

## Commit Gate
- Before committing, verify no secret-like content was introduced.
- If secret-like content is found, stop changes and replace with placeholders immediately.

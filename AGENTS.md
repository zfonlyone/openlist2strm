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

## Deployment Convention
- Dev repo path: `/root/code/docker/openlist2strm`
- Target deploy path: `/etc/media-server/openlist2strm`
- Deployment script must sync local project source to target path first, then run Docker build/start in that target path.
- Runtime `.env` must live in target path only (`/etc/media-server/openlist2strm/.env`), never in this repository.
- Keep persistent runtime data outside source sync scope (for example: `config/`, `data/`, runtime media output directories).
- Do not assume source repo changes are live until target path has been synced and compose/service restarted.

## Deploy / Verify Flow
1. Modify code in `/root/code/docker/openlist2strm`
2. Run project-level validation/build as needed
3. Sync repo → target path
4. Rebuild/restart from `/etc/media-server/openlist2strm`
5. Verify:
   - `docker compose ps`
   - `docker inspect <container>`
   - local port / local URL
   - public URL if exposed

## Commit Gate
- Before committing, verify no secret-like content was introduced.
- If secret-like content is found, stop changes and replace with placeholders immediately.

# AGENTS

## Security Baseline
- **不要直接修改env中的密钥和容器密钥，需要得到我的同意才可以。**
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
- Dev repo path: `/root/code/media-server/openlist2strm`
- Target deploy path: `/etc/media-server/openlist2strm`
- Docker image must be built in the source repository, not in the target runtime path.
- Runtime path keeps config/data/control files only; source code must not live under `/etc/media-server/openlist2strm`.
- Deployment entrypoint is `sudo ./scripts/deploy.sh` from the source repository.
- Runtime `.env` must live in target path only (`/etc/media-server/openlist2strm/.env`), never in this repository.
- Keep persistent runtime data outside source sync scope (for example: `config/`, `data/`, runtime media output directories).
- Do not assume source repo changes are live until `sudo ./scripts/deploy.sh` has rebuilt and restarted the service.

## Deploy / Verify Flow
1. Modify code in `/root/code/media-server/openlist2strm`
2. Run project-level validation/build as needed
3. Run `sudo ./scripts/deploy.sh` in the source repo
4. Rebuild image in source path and restart from `/etc/media-server/openlist2strm`
5. Verify:
   - `docker compose ps`
   - `docker inspect <container>`
   - local port / local URL
   - public URL if exposed

## Commit Gate
- Before committing, verify no secret-like content was introduced.
- If secret-like content is found, stop changes and replace with placeholders immediately.

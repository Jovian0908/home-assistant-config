# Push this repo to GitHub

This repo is fully scaffolded and committed locally. The remote push is a single user step because the embedded `gh` keyring token is invalid and the PAT MCP doesn't have repo-creation scope. Two paths:

## Option A: gh CLI (recommended)

```bash
cd C:\Users\jovia\home-assistant-config
gh auth login -h github.com               # one-time interactive
gh repo create home-assistant-config --public --source=. --push
```

`gh repo create --source=. --push` creates the remote, sets the upstream, and pushes the existing commit in one call.

## Option B: web UI + git push

1. Open https://github.com/new
2. Name: `home-assistant-config`
3. Public; do NOT initialize with README/license/.gitignore (we already have them)
4. Create
5. Then locally:

```bash
cd C:\Users\jovia\home-assistant-config
git remote add origin https://github.com/Jovian0908/home-assistant-config.git
git push -u origin main
```

## After the push

1. CI will start running on the first push. Watch:
   ```
   gh run watch
   ```
2. Verify all 5 jobs go green: ha-core-check (stable/beta/dev), python-lint, yaml-lint, actionlint, zizmor.
3. The README's CI badge will turn green automatically.
4. Update README's clone URL if the username differs from the placeholder.

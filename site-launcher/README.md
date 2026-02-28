# Site Launcher

AI-first tool for spinning up new Lozzalingo-powered websites. Claude Code handles the discovery, scaffolding, and deployment — you just answer a few questions.

## How to Use

1. Open Claude Code in the `Lozzalingo-python/` directory
2. Say: **"Launch a new site"** (or open this directory and let Claude read `CLAUDE.md`)
3. Answer the questions — site name, features, branding, domain
4. Claude copies the starter template, customizes everything, and gets it running
5. Optionally deploy to production with guided server setup

## What You Get

- A fully configured Flask app with your chosen Lozzalingo modules
- Custom branding (colors, theme, content)
- Docker setup ready for production
- Nginx + SSL configuration (if deploying)
- Site-specific `CLAUDE.md` for future development

## Prerequisites

- Python 3.11+
- The `lozzalingo-framework` directory (sibling to your new site)
- For deployment: SSH access to a server, Docker, Nginx

## Files

| File | Purpose |
|------|---------|
| `CLAUDE.md` | AI instructions — the 5-phase launch flow |
| `DEPLOY.md` | Production deployment reference (humans + AI) |
| `README.md` | This file |

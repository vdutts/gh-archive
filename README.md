# GitHub Starred Repos Backup

Auto-backup all starred repos from any GitHub account to Cloudflare R2.

## ONE COMMAND

```bash
python3 go.py
```

That's it. Does EVERYTHING:
1. Creates venv
2. Installs dependencies  
3. Creates .env template
4. Tests the backup
5. Tells you what to do next

## Usage

```bash
# Test run (default)
python3 go.py

# Real backup
python3 go.py --max-repos 10

# All repos
python3 go.py
```

## What You Need

1. **GitHub Token**: Create at github.com/settings/tokens with `Starring` + `Metadata` + `Contents` (read-only)
2. **R2 Credentials**: Already configured in the script

## Files

- `backup_starred_repos.py` - Main script
- `setup.py` - One-click setup
- `config/` - Configuration files
- `.env` - Your GitHub token (create this)

Runs weekly via GitHub Actions. Costs $0/month.
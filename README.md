# GitHub Starred Repos Backup

Auto-backup all starred repos from any GitHub account to Cloudflare R2.

## Features

- ✅ **Automated daily backups** via GitHub Actions
- ✅ **Deterministic naming** with owner + repo slug
- ✅ **Only keeps latest backup** per repo (no duplicates)
- ✅ **Comprehensive manifest** with metadata, contributors, topics
- ✅ **Free tier friendly** - uses <150 min/month on GitHub Actions
- ✅ **Cloudflare R2 storage** - 10GB free tier

## Quick Start

### Local Testing

```bash
# One command setup + test
python3 go.py --max-repos 5

# Backup all starred repos
python3 go.py
```

### Production (GitHub Actions)

1. **Add GitHub Secrets** at `Settings → Secrets → Actions`:
   - `GH_TOKEN` - Your GitHub personal access token
   - `GH_USER_ID` - Target user's GitHub ID (e.g., `***REMOVED***`)
   - `GH_USERNAME` - Target user's username (optional fallback)
   - `R2_ACCOUNT_ID` - Cloudflare R2 account ID
   - `R2_ACCESS_KEY_ID` - R2 access key
   - `R2_SECRET_ACCESS_KEY` - R2 secret key
   - `R2_BUCKET_NAME` - R2 bucket name (e.g., `gh-starred-backups`)

2. **Push to GitHub** - Workflow runs automatically daily at 2 AM UTC

3. **Manual trigger** - Go to `Actions → Backup Starred Repos → Run workflow`

## Setup Details

### GitHub Token Permissions

Create token at [github.com/settings/tokens](https://github.com/settings/tokens) with:
- ✅ `Starring` (read-only) - **REQUIRED** to fetch starred repos
- ✅ `Metadata` (read-only) - Repo metadata
- ✅ `Contents` (read-only) - Clone repos

### Cloudflare R2 Setup

1. Create R2 bucket at [dash.cloudflare.com](https://dash.cloudflare.com)
2. Generate API token with R2 read/write permissions
3. Add credentials to GitHub Secrets

## How It Works

1. Fetches starred repos from target GitHub user (by ID with username fallback)
2. Clones each repo as a git mirror
3. Creates zip archive with unique naming: `YYYYMMDD_hash_owner_repo.zip`
4. Deletes old backups for the same repo (keeps only latest)
5. Uploads to Cloudflare R2
6. Generates comprehensive JSON manifest with metadata

## Files

- `backup_starred_repos.py` - Main backup script
- `go.py` - One-command setup + runner
- `.github/workflows/backup.yml` - GitHub Actions workflow
- `config/` - Configuration examples
- `.env.example` - Environment variable template

## Cost

**$0/month** on GitHub Free tier:
- GitHub Actions: 2,000 min/month (uses ~150 min/month for daily backups)
- Cloudflare R2: 10GB free storage
- Public repos get unlimited Actions minutes

## License

MIT
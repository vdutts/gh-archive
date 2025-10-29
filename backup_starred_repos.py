#!/usr/bin/env python3
"""
GitHub Starred Repositories Backup Script
Automatically fetches starred repos, clones them, and uploads to Cloudflare R2
"""

import os
import sys
import json
import shutil
import zipfile
import tempfile
import argparse
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

import requests
import boto3
from git import Repo
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class GitHubStarredBackup:
    def __init__(self):
        # GitHub configuration
        self.github_token = os.getenv('GH_TOKEN')
        self.github_user_id = os.getenv('GH_USER_ID')  # Primary: More reliable
        self.github_username = os.getenv('GH_USERNAME')  # Fallback: If no user ID
        self.resolved_username = None  # Actual username resolved from ID or provided
        
        # R2 configuration
        self.r2_account_id = os.getenv('R2_ACCOUNT_ID')
        self.r2_access_key = os.getenv('R2_ACCESS_KEY_ID')
        self.r2_secret_key = os.getenv('R2_SECRET_ACCESS_KEY')
        self.r2_bucket = os.getenv('R2_BUCKET_NAME')
        
        # Initialize R2 client
        self.r2_client = boto3.client(
            's3',
            endpoint_url=f'https://{self.r2_account_id}.r2.cloudflarestorage.com',
            aws_access_key_id=self.r2_access_key,
            aws_secret_access_key=self.r2_secret_key,
            region_name='auto'
        )
        
        # Session for GitHub API
        self.session = requests.Session()
        if self.github_token:
            self.session.headers.update({
                'Authorization': f'token {self.github_token}',
                'Accept': 'application/vnd.github.v3+json'
            })
        
        # Manifest data
        self.manifest = {
            'backup_info': {
                'created_at': datetime.now().isoformat(),
                'github_username': self.github_username,
                'total_repos': 0,
                'backup_id': self.generate_backup_id()
            },
            'starred_lists': {},
            'repositories': {},
            'lookup': {}
        }
    
    def generate_backup_id(self) -> str:
        """Generate unique backup ID"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"backup_{timestamp}"
    
    def generate_repo_id(self, repo_full_name: str, repo_url: str) -> str:
        """Generate unique repository identifier with owner for deterministic matching"""
        # Create hash from repo URL for uniqueness
        hash_obj = hashlib.md5(repo_url.encode())
        hash_hex = hash_obj.hexdigest()[:8]
        timestamp = datetime.now().strftime('%Y%m%d')
        # Use owner_reponame format for deterministic matching
        slug = repo_full_name.replace('/', '_')
        return f"{timestamp}_{hash_hex}_{slug}"
    
    def get_user_info(self) -> Dict:
        """Get target user info from GitHub API with fallback logic"""
        user_info = {}
        
        # Try User ID first (most reliable)
        if self.github_user_id:
            try:
                self.log(f"🔍 Fetching user info by ID: {self.github_user_id}")
                self.log(f"📡 API Call: GET https://api.github.com/user/{self.github_user_id}")
                response = self.session.get(f'https://api.github.com/user/{self.github_user_id}')
                response.raise_for_status()
                user_info = response.json()
                self.resolved_username = user_info['login']
                self.log(f"✅ Resolved ID {self.github_user_id} → {self.resolved_username}")
                self.log(f"👤 User: {user_info.get('name', 'N/A')} (@{self.resolved_username})")
                self.log(f"📊 Public repos: {user_info.get('public_repos', 0)}, Followers: {user_info.get('followers', 0)}")
                return user_info
            except requests.RequestException as e:
                self.log(f"❌ Failed to fetch by ID {self.github_user_id}: {e}", 'WARNING')
        
        # Fallback to username
        if self.github_username:
            try:
                self.log(f"🔄 Falling back to username: {self.github_username}")
                self.log(f"📡 API Call: GET https://api.github.com/users/{self.github_username}")
                response = self.session.get(f'https://api.github.com/users/{self.github_username}')
                response.raise_for_status()
                user_info = response.json()
                self.resolved_username = user_info['login']
                self.github_user_id = str(user_info['id'])  # Cache the ID for future use
                self.log(f"✅ Resolved username {self.github_username} → ID {self.github_user_id}")
                self.log(f"👤 User: {user_info.get('name', 'N/A')} (@{self.resolved_username})")
                return user_info
            except requests.RequestException as e:
                self.log(f"❌ Failed to fetch by username {self.github_username}: {e}", 'ERROR')
        
        self.log("❌ No valid user ID or username provided", 'ERROR')
        return {}
    
    def log(self, message: str, level: str = 'INFO'):
        """Simple logging function"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] {level}: {message}")
    
    def get_starred_repos(self) -> List[Dict]:
        """Fetch all starred repositories from GitHub API with enhanced metadata"""
        # Get target user info first
        if not self.resolved_username:
            user_info = self.get_user_info()
            if not user_info:
                self.log("Failed to get user info", 'ERROR')
                return []
            self.log(f"🎯 Target: {self.resolved_username} (ID: {self.github_user_id})")
        
        self.log(f"Fetching starred repositories...")
        starred_repos = []
        page = 1
        
        while True:
            # Use the most reliable method available
            if self.github_user_id:
                url = f'https://api.github.com/user/{self.github_user_id}/starred'
            else:
                url = f'https://api.github.com/users/{self.resolved_username}/starred'
            params = {'page': page, 'per_page': 100}
            
            try:
                self.log(f"📡 API Call: GET {url}?page={page}&per_page=100")
                response = self.session.get(url, params=params)
                response.raise_for_status()
                
                repos = response.json()
                if not repos:
                    self.log(f"📄 Page {page}: No more repos (end of list)")
                    break
                
                self.log(f"📄 Page {page}: Found {len(repos)} repos")
                
                # Enhance each repo with additional metadata
                for i, repo in enumerate(repos, 1):
                    self.log(f"🔍 Processing repo {i}/{len(repos)}: {repo['full_name']}")
                    enhanced_repo = self.enhance_repo_metadata(repo)
                    starred_repos.append(enhanced_repo)
                
                self.log(f"✅ Page {page} complete - Total so far: {len(starred_repos)} repos")
                page += 1
                
            except requests.RequestException as e:
                self.log(f"Error fetching starred repos: {e}", 'ERROR')
                break
        
        if len(starred_repos) == 0:
            self.log(f"⚠️  ZERO starred repositories found for {self.resolved_username}!")
            self.log(f"🤔 This could mean:")
            self.log(f"   • User has no starred repos")
            self.log(f"   • GitHub token lacks permissions")
            self.log(f"   • User's starred repos are private")
            self.log(f"   • Wrong user ID/username")
        else:
            self.log(f"🎉 Total starred repositories: {len(starred_repos)}")
        
        return starred_repos
    
    def enhance_repo_metadata(self, repo: Dict) -> Dict:
        """Enhance repository with additional metadata"""
        enhanced = repo.copy()
        
        # Get contributors
        try:
            contributors_url = repo['contributors_url']
            contributors_response = self.session.get(contributors_url)
            if contributors_response.status_code == 200:
                enhanced['contributors'] = contributors_response.json()[:10]  # Top 10 contributors
            else:
                enhanced['contributors'] = []
        except:
            enhanced['contributors'] = []
        
        # Get languages
        try:
            languages_url = repo['languages_url']
            languages_response = self.session.get(languages_url)
            if languages_response.status_code == 200:
                enhanced['languages'] = languages_response.json()
            else:
                enhanced['languages'] = {}
        except:
            enhanced['languages'] = {}
        
        # Get topics/tags
        try:
            topics_url = f"{repo['url']}/topics"
            topics_response = self.session.get(topics_url, headers={'Accept': 'application/vnd.github.mercy-preview+json'})
            if topics_response.status_code == 200:
                enhanced['topics'] = topics_response.json().get('names', [])
            else:
                enhanced['topics'] = []
        except:
            enhanced['topics'] = []
        
        return enhanced
    
    def get_starred_lists(self) -> Dict:
        """Fetch user's starred lists/categories (if available)"""
        # Note: GitHub doesn't have public API for starred lists yet
        # This is a placeholder for when the feature becomes available
        # For now, we'll categorize by language and topics
        self.log("Organizing repositories by categories...")
        
        categories = {
            'uncategorized': [],
            'by_language': {},
            'by_topic': {}
        }
        
        return categories
    
    def check_existing_backup(self, repo_full_name: str, repo_url: str) -> Dict:
        """Check if repository backup already exists in R2 - CATCHES BOTH OLD AND NEW FORMATS"""
        try:
            # Create slugs for matching
            slug_with_owner = repo_full_name.replace('/', '_')  # New format: owner_repo
            repo_name_only = repo_full_name.split('/')[-1]  # Old format: just repo name
            
            # List all objects in bucket
            response = self.r2_client.list_objects_v2(
                Bucket=self.r2_bucket
            )
            
            if 'Contents' not in response:
                return {'exists': False}
            
            # Find ALL backups of this repo (both old and new naming schemes)
            existing_backups = []
            for obj in response['Contents']:
                filename = obj['Key']
                # Match new format: _{owner_repo}.zip OR old format: _{repo}.zip
                if filename.endswith(f"_{slug_with_owner}.zip") or filename.endswith(f"_{repo_name_only}.zip"):
                    existing_backups.append({
                        'filename': filename,
                        'last_modified': obj['LastModified'],
                        'size': obj['Size']
                    })
            
            if existing_backups:
                existing_backups.sort(key=lambda x: x['last_modified'], reverse=True)
                return {
                    'exists': True,
                    'count': len(existing_backups),
                    'latest': existing_backups[0],
                    'all': existing_backups
                }
            
            return {'exists': False}
            
        except Exception as e:
            self.log(f"Error checking existing backup for {repo_full_name}: {e}", 'WARNING')
            return {'exists': False}
    
    def clone_repository(self, repo_url: str, repo_name: str, temp_dir: Path) -> Optional[Path]:
        """Clone repository to temporary directory"""
        clone_path = temp_dir / repo_name
        
        try:
            self.log(f"Cloning {repo_name}...")
            Repo.clone_from(repo_url, clone_path, mirror=True)
            return clone_path
        except Exception as e:
            self.log(f"Error cloning {repo_name}: {e}", 'ERROR')
            return None
    
    def create_zip_archive(self, repo_path: Path, repo_id: str, temp_dir: Path) -> Optional[Path]:
        """Create zip archive of the cloned repository"""
        zip_path = temp_dir / f"{repo_id}.zip"
        
        try:
            self.log(f"Creating zip archive for {repo_id}...")
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for file_path in repo_path.rglob('*'):
                    if file_path.is_file():
                        arcname = file_path.relative_to(repo_path)
                        zipf.write(file_path, arcname)
            
            self.log(f"Zip created: {zip_path.name} ({zip_path.stat().st_size / 1024 / 1024:.1f} MB)")
            return zip_path
        except Exception as e:
            self.log(f"Error creating zip for {repo_id}: {e}", 'ERROR')
            return None
    
    def upload_to_r2(self, zip_path: Path) -> bool:
        """Upload zip file to Cloudflare R2"""
        try:
            self.log(f"Uploading {zip_path.name} to R2...")
            
            with open(zip_path, 'rb') as f:
                self.r2_client.upload_fileobj(
                    f,
                    self.r2_bucket,
                    zip_path.name,
                    ExtraArgs={'ContentType': 'application/zip'}
                )
            
            self.log(f"Successfully uploaded {zip_path.name}")
            return True
        except Exception as e:
            self.log(f"Error uploading {zip_path.name}: {e}", 'ERROR')
            return False
    
    def backup_repository(self, repo: Dict, temp_dir: Path, skip_existing: bool = True) -> bool:
        """Backup a single repository and update manifest"""
        repo_name = repo['name']
        repo_full_name = repo['full_name']
        clone_url = repo['clone_url']
        
        # Generate unique repo ID with owner for deterministic matching
        repo_id = self.generate_repo_id(repo_full_name, clone_url)
        
        # Check for existing backups using deterministic full name
        existing_check = self.check_existing_backup(repo_full_name, clone_url)
        if skip_existing and existing_check['exists']:
            latest_backup = existing_check['latest']
            backup_age = (datetime.now(latest_backup['last_modified'].tzinfo) - latest_backup['last_modified']).days
            
            self.log(f"📁 Found {existing_check['count']} existing backup(s) for {repo_name}")
            self.log(f"📅 Latest backup: {latest_backup['filename']} ({backup_age} days old)")
            
            # Always create new backup (repos change over time)
            self.log(f"🔄 Creating fresh backup (repos change over time)...")
        elif existing_check['exists']:
            self.log(f"📁 Found {existing_check['count']} existing backup(s), but continuing with fresh backup...")
        
        # Clone repository
        repo_path = self.clone_repository(clone_url, repo_name, temp_dir)
        if not repo_path:
            self.add_to_manifest(repo, repo_id, 'failed_clone')
            return False
        
        # Create zip archive with unique name
        zip_path = self.create_zip_archive(repo_path, repo_id, temp_dir)
        if not zip_path:
            self.add_to_manifest(repo, repo_id, 'failed_zip')
            return False
        
        # Delete old backups for this repo before uploading new one
        if existing_check['exists']:
            for old in existing_check['all']:
                try:
                    self.r2_client.delete_object(Bucket=self.r2_bucket, Key=old['filename'])
                    self.log(f"🗑️ Deleted old backup: {old['filename']}")
                except Exception as e:
                    self.log(f"Error deleting {old['filename']}: {e}", 'WARNING')
        # Upload to R2
        success = self.upload_to_r2(zip_path)
        
        # Add to manifest with backup info
        status = 'success' if success else 'failed_upload'
        backup_info = {'is_update': existing_check['exists']}
        self.add_to_manifest(repo, repo_id, status, zip_path.name, backup_info)
        
        # Cleanup
        try:
            shutil.rmtree(repo_path)
            zip_path.unlink()
        except Exception as e:
            self.log(f"Error cleaning up files: {e}", 'WARNING')
        
        return success
    
    def add_to_manifest(self, repo: Dict, repo_id: str, status: str, zip_filename: str = None, backup_info: Dict = None):
        """Add repository to manifest with comprehensive metadata"""
        # Main repository entry
        self.manifest['repositories'][repo_id] = {
            'original_name': repo['name'],
            'full_name': repo['full_name'],
            'unique_id': repo_id,
            'backup_status': status,
            'zip_filename': zip_filename,
            'metadata': {
                'description': repo.get('description', ''),
                'homepage': repo.get('homepage', ''),
                'language': repo.get('language', ''),
                'languages': repo.get('languages', {}),
                'topics': repo.get('topics', []),
                'stars_count': repo.get('stargazers_count', 0),
                'forks_count': repo.get('forks_count', 0),
                'watchers_count': repo.get('watchers_count', 0),
                'size': repo.get('size', 0),
                'created_at': repo.get('created_at', ''),
                'updated_at': repo.get('updated_at', ''),
                'pushed_at': repo.get('pushed_at', ''),
                'clone_url': repo.get('clone_url', ''),
                'ssh_url': repo.get('ssh_url', ''),
                'html_url': repo.get('html_url', ''),
                'license': repo.get('license', {}).get('name', '') if repo.get('license') else '',
                'is_fork': repo.get('fork', False),
                'is_archived': repo.get('archived', False),
                'is_private': repo.get('private', False),
                'default_branch': repo.get('default_branch', 'main')
            },
            'owner': {
                'login': repo['owner']['login'],
                'type': repo['owner']['type'],
                'html_url': repo['owner']['html_url']
            },
            'contributors': repo.get('contributors', []),
            'backed_up_at': datetime.now().isoformat()
        }
        
        # Add to lookup table for easy searching
        self.manifest['lookup'][repo['name']] = repo_id
        self.manifest['lookup'][repo['full_name']] = repo_id
        
        # Categorize by language
        language = repo.get('language', 'Unknown')
        if language not in self.manifest['starred_lists'].get('by_language', {}):
            self.manifest['starred_lists'].setdefault('by_language', {})[language] = []
        self.manifest['starred_lists']['by_language'][language].append(repo_id)
        
        # Categorize by topics
        for topic in repo.get('topics', []):
            if topic not in self.manifest['starred_lists'].get('by_topic', {}):
                self.manifest['starred_lists'].setdefault('by_topic', {})[topic] = []
            self.manifest['starred_lists']['by_topic'][topic].append(repo_id)
        
        # Update total count
        self.manifest['backup_info']['total_repos'] += 1
    
    def save_manifest(self, temp_dir: Path) -> Optional[Path]:
        """Save manifest to JSON file and upload to R2, delete old manifests"""
        try:
            # Delete all old manifest files first
            try:
                response = self.r2_client.list_objects_v2(Bucket=self.r2_bucket)
                if 'Contents' in response:
                    for obj in response['Contents']:
                        if obj['Key'].startswith('manifest_backup_') and obj['Key'].endswith('.json'):
                            self.r2_client.delete_object(Bucket=self.r2_bucket, Key=obj['Key'])
                            self.log(f"🗑️ Deleted old manifest: {obj['Key']}")
            except Exception as e:
                self.log(f"Error deleting old manifests: {e}", 'WARNING')
            
            # Create manifest filename with backup ID
            backup_id = self.manifest['backup_info']['backup_id']
            manifest_filename = f"manifest_{backup_id}.json"
            manifest_path = temp_dir / manifest_filename
            
            # Save manifest locally
            with open(manifest_path, 'w') as f:
                json.dump(self.manifest, f, indent=2, default=str)
            
            self.log(f"Manifest saved: {manifest_filename}")
            
            # Upload manifest to R2
            try:
                with open(manifest_path, 'rb') as f:
                    self.r2_client.upload_fileobj(
                        f,
                        self.r2_bucket,
                        manifest_filename,
                        ExtraArgs={'ContentType': 'application/json'}
                    )
                self.log(f"Manifest uploaded to R2: {manifest_filename}")
            except Exception as e:
                self.log(f"Error uploading manifest: {e}", 'WARNING')
            
            return manifest_path
            
        except Exception as e:
            self.log(f"Error saving manifest: {e}", 'ERROR')
            return None
    
    def run_backup(self, dry_run: bool = False, max_repos: Optional[int] = None):
        """Run the complete backup process with manifest generation"""
        self.log("Starting GitHub starred repositories backup...")
        
        if dry_run:
            self.log("DRY RUN MODE - No actual backups will be performed")
        
        # Get starred repositories
        starred_repos = self.get_starred_repos()
        if not starred_repos:
            self.log("No starred repositories found", 'WARNING')
            return
        
        # Limit repos if specified
        if max_repos:
            starred_repos = starred_repos[:max_repos]
            self.log(f"Limited to first {max_repos} repositories")
        
        # Initialize starred lists in manifest
        self.manifest['starred_lists'] = self.get_starred_lists()
        
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            success_count = 0
            failed_repos = []
            
            for i, repo in enumerate(starred_repos, 1):
                repo_name = repo['name']
                repo_id = self.generate_repo_id(repo_name, repo['clone_url'])
                self.log(f"Processing {i}/{len(starred_repos)}: {repo_name} -> {repo_id}")
                
                if dry_run:
                    self.log(f"Would backup: {repo['full_name']} as {repo_id}")
                    # Add to manifest even in dry run for structure preview
                    self.add_to_manifest(repo, repo_id, 'dry_run')
                    continue
                
                if self.backup_repository(repo, temp_path):
                    success_count += 1
                else:
                    failed_repos.append(repo_name)
            
            # Save and upload manifest
            if not dry_run:
                manifest_path = self.save_manifest(temp_path)
                if manifest_path:
                    self.log(f"Manifest contains {len(self.manifest['repositories'])} repositories")
                    self.log(f"Categories: {len(self.manifest['starred_lists']['by_language'])} languages, {len(self.manifest['starred_lists']['by_topic'])} topics")
            else:
                # In dry run, just show manifest structure
                self.log("\n📋 MANIFEST PREVIEW:")
                self.log(f"Total repos: {len(self.manifest['repositories'])}")
                self.log(f"Languages: {list(self.manifest['starred_lists']['by_language'].keys())[:10]}...")
                self.log(f"Topics: {list(self.manifest['starred_lists']['by_topic'].keys())[:10]}...")
        
        # Summary
        self.log("=" * 50)
        self.log(f"Backup completed!")
        self.log(f"Total repositories: {len(starred_repos)}")
        self.log(f"Successfully backed up: {success_count}")
        self.log(f"Failed: {len(failed_repos)}")
        
        if failed_repos:
            self.log(f"Failed repositories: {', '.join(failed_repos)}")
        
        if not dry_run:
            backup_id = self.manifest['backup_info']['backup_id']
            self.log(f"\n🎯 BACKUP SUMMARY:")
            self.log(f"Backup ID: {backup_id}")
            self.log(f"Manifest: manifest_{backup_id}.json")
            self.log(f"Repository files: [timestamp]_[hash]_[name].zip")
            self.log(f"Total storage used: Check R2 bucket 'gh-starred-backups'")

def main():
    parser = argparse.ArgumentParser(description='Backup GitHub starred repositories to Cloudflare R2 with comprehensive manifest')
    parser.add_argument('--dry-run', action='store_true', help='Perform a dry run without actual backups (shows manifest structure)')
    parser.add_argument('--max-repos', type=int, help='Maximum number of repositories to process')
    
    args = parser.parse_args()
    
    # Validate environment variables
    required_vars = [
        'GH_TOKEN',
        'R2_ACCOUNT_ID',
        'R2_ACCESS_KEY_ID',
        'R2_SECRET_ACCESS_KEY',
        'R2_BUCKET_NAME'
    ]
    
    # Check that at least one user identifier is provided
    if not os.getenv('GH_USER_ID') and not os.getenv('GH_USERNAME'):
        print("Error: Must provide either GH_USER_ID or GH_USERNAME (or both)")
        print("GH_USER_ID is preferred for reliability")
        sys.exit(1)
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
        print("Please set these variables in your .env file")
        sys.exit(1)
    
    # Run backup
    backup = GitHubStarredBackup()
    backup.run_backup(dry_run=args.dry_run, max_repos=args.max_repos)

if __name__ == '__main__':
    main()

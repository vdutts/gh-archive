#!/usr/bin/env python3
"""
One-click setup for GitHub starred repos backup with venv
"""

import os
import subprocess
import sys
import venv
from pathlib import Path

def run_cmd(cmd, cwd=None, shell_env=None):
    """Run command and return success"""
    try:
        env = os.environ.copy()
        if shell_env:
            env.update(shell_env)
        subprocess.run(cmd, shell=True, check=True, cwd=cwd, env=env)
        return True
    except subprocess.CalledProcessError:
        return False

def main():
    print("🚀 Setting up GitHub starred repos backup with venv...")
    
    venv_path = Path("venv")
    
    # 1. Create venv if it doesn't exist
    if not venv_path.exists():
        print("🏗️  Creating virtual environment...")
        venv.create(venv_path, with_pip=True)
        print("✅ Virtual environment created!")
    else:
        print("✅ Virtual environment already exists!")
    
    # 2. Determine activation script path
    if sys.platform == "win32":
        pip_path = venv_path / "Scripts" / "pip"
        python_path = venv_path / "Scripts" / "python"
    else:
        pip_path = venv_path / "bin" / "pip"
        python_path = venv_path / "bin" / "python"
    
    # 3. Install dependencies in venv
    print("📦 Installing Python dependencies in venv...")
    if not run_cmd(f"{pip_path} install -r requirements.txt"):
        print("❌ Failed to install dependencies in venv")
        sys.exit(1)
    
    # 2. Create .env if it doesn't exist
    if not Path(".env").exists():
        print("⚙️  Creating .env file...")
        with open(".env", "w") as f:
            f.write("# GitHub Configuration\n")
            f.write("GH_TOKEN=your_github_personal_access_token_here\n")
            f.write("GH_USER_ID=your_target_user_id_here\n")
            f.write("GH_USERNAME=your_target_username_here\n\n")
            f.write("# Cloudflare R2 Configuration\n")
            f.write("R2_ACCOUNT_ID=your_r2_account_id_here\n")
            f.write("R2_ACCESS_KEY_ID=your_r2_access_key_here\n")
            f.write("R2_SECRET_ACCESS_KEY=your_r2_secret_key_here\n")
            f.write("R2_BUCKET_NAME=gh-starred-backups\n")
        print("✅ Created .env file - ADD YOUR CREDENTIALS!")
    
    # 4. Test script in venv
    print("🧪 Testing backup script in venv...")
    if run_cmd(f"{python_path} backup_starred_repos.py --dry-run --max-repos 1"):
        print("✅ Script works in venv!")
    else:
        print("❌ Script test failed - check your .env file")
        print("Make sure to fill out your .env file with real credentials!")
    
    print("\n🎉 Setup complete!")
    print("\n🔥 ONE COMMAND TO RULE THEM ALL:")
    print("   python3 run.py --dry-run")
    print("   python3 run.py")
    print("\n💡 The run.py script automatically handles venv activation!")

if __name__ == "__main__":
    main()

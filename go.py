#!/usr/bin/env python3
"""
ONE FUCKING COMMAND TO DO EVERYTHING
- Creates venv
- Installs deps
- Creates .env template
- Tests everything
- Runs the backup
"""

import os
import subprocess
import sys
import venv
from pathlib import Path

def run_cmd(cmd, cwd=None):
    """Run command and return success"""
    try:
        result = subprocess.run(cmd, shell=True, check=True, cwd=cwd, 
                              capture_output=True, text=True)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr

def main():
    print("🚀 SETTING UP EVERYTHING IN ONE COMMAND...")
    
    venv_path = Path("venv")
    
    # 1. Create venv if needed
    if not venv_path.exists():
        print("🏗️  Creating virtual environment...")
        venv.create(venv_path, with_pip=True)
        print("✅ Virtual environment created!")
    
    # 2. Get venv paths
    if sys.platform == "win32":
        pip_path = venv_path / "Scripts" / "pip"
        python_path = venv_path / "Scripts" / "python"
    else:
        pip_path = venv_path / "bin" / "pip"
        python_path = venv_path / "bin" / "python"
    
    # 3. Install dependencies
    print("📦 Installing dependencies...")
    success, output = run_cmd(f"{pip_path} install -r requirements.txt")
    if not success:
        print(f"❌ Failed to install dependencies: {output}")
        sys.exit(1)
    
    # 4. Create .env if needed
    if not Path(".env").exists():
        print("⚙️  Creating .env template...")
        with open(".env", "w") as f:
            f.write("GH_TOKEN=your_github_pat\n")
            f.write("GH_USER_ID=target_github_user_id\n")
            f.write("GH_USERNAME=target_github_username\n\n")
            f.write("R2_ACCOUNT_ID=r2_account_id\n")
            f.write("R2_ACCESS_KEY_ID=r2_access_key\n")
            f.write("R2_SECRET_ACCESS_KEY=r2_secret_key\n")
            f.write("R2_BUCKET_NAME=r2_bucket_name\n")
        print("✅ Created .env - FILL IT OUT WITH REAL VALUES!")
        print("❌ Cannot continue without real credentials in .env")
        return
    
    # 5. Parse arguments to decide what to do
    if len(sys.argv) > 1:
        # Pass all args to backup script
        args = " ".join(sys.argv[1:])
        print(f"🚀 Running backup with args: {args}")
        success, output = run_cmd(f"{python_path} backup_starred_repos.py {args}")
        if success:
            print(output)
        else:
            print(f"❌ Backup failed: {output}")
            sys.exit(1)
    else:
        # Default dry run
        print("🧪 Running test backup (dry run)...")
        success, output = run_cmd(f"{python_path} backup_starred_repos.py --dry-run --max-repos 3")
        print(output)
        
        if "No starred repositories found" in output:
            print("\n⚠️  this target gh user has 0 starred repos!")
            print("Either:")
            print("1. The account has no starred repos")
            print("2. Your GitHub token doesn't have access")
            print("3. Wrong user ID/username")
        elif success:
            print("\n🎉 EVERYTHING WORKS! Now run:")
            print("   python3 go.py --max-repos 10  # Real backup")
        else:
            print(f"\n❌ Test failed: {output}")

if __name__ == "__main__":
    main()

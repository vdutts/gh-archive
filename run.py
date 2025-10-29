#!/usr/bin/env python3
"""
Wrapper script that automatically uses venv
"""

import subprocess
import sys
from pathlib import Path

def main():
    venv_path = Path("venv")
    
    if not venv_path.exists():
        print("❌ Virtual environment not found! Run 'python3 setup.py' first")
        sys.exit(1)
    
    # Determine python path in venv
    if sys.platform == "win32":
        python_path = venv_path / "Scripts" / "python"
    else:
        python_path = venv_path / "bin" / "python"
    
    # Pass all arguments to the backup script
    cmd = [str(python_path), "backup_starred_repos.py"] + sys.argv[1:]
    
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        sys.exit(e.returncode)

if __name__ == "__main__":
    main()

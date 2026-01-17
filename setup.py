"""
FALLBACK SETUP SCRIPT
=====================
Use this if 'boot.sh' is missing or fails.
Run: python3 setup.py
"""

import os
import sys
import subprocess
import venv

def run_command(cmd):
    try:
        subprocess.check_call(cmd, shell=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running: {cmd}")
        sys.exit(1)

def main():
    print("🛠️  AUTONOMOUS SETUP (PYTHON FALLBACK)")
    print("=======================================")

    # 1. Verify Repo Integrity
    if not os.path.exists("orchestrator.py"):
        print("❌ CRITICAL: orchestrator.py missing.")
        print("   Did you run 'git pull origin main'?")
        sys.exit(1)

    # 2. Install Dependencies
    print("⬇️  Installing dependencies...")
    run_command(f"{sys.executable} -m pip install -r requirements.txt")

    # 3. Create __init__ files
    for folder in ["security", "integrations", "modules"]:
        if not os.path.exists(folder):
            os.makedirs(folder)
        open(f"{folder}/__init__.py", "a").close()

    # 4. Prompt for Key
    key = os.environ.get("COMMANDER_ONE_KEY")
    if not key:
        print("\n🔑 ENTER COMMANDER ONE KEY:")
        key = input("   > ").strip()
        os.environ["COMMANDER_ONE_KEY"] = key

    # 5. Launch
    print("\n🚀 Launching Orchestrator...")
    # Pass the env var explicitly to the subprocess
    env = os.environ.copy()
    env["COMMANDER_ONE_KEY"] = key
    subprocess.call([sys.executable, "orchestrator.py"], env=env)

if __name__ == "__main__":
    main()

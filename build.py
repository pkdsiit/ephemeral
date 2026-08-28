#!/usr/bin/env python3
"""
Production Build Script for Render Deployment.
Runs database migrations and safe initialization during build phase.
"""
import os
import sys
import subprocess


def run_migrations():
    db_url = os.environ.get('DATABASE_URL', '').strip()
    
    if not db_url:
        print("[Build] No DATABASE_URL provided at build time. Skipping database migrations during build.")
        print("[Build] Migrations will run on startup once PostgreSQL is linked.")
        return

    print("[Build] Running PostgreSQL database migrations (flask db upgrade)...")
    try:
        res = subprocess.run([sys.executable, "-m", "flask", "db", "upgrade"], capture_output=True, text=True)
        if res.returncode == 0:
            print("[Build] Database migrations applied successfully.")
            if res.stdout:
                print(res.stdout)
        else:
            print(f"[Build] Migration notice (exit code {res.returncode}):")
            print(res.stderr or res.stdout)
            print("[Build] Continuing build...")
    except Exception as e:
        print(f"[Build] Migration execution note: {e}")


if __name__ == '__main__':
    run_migrations()

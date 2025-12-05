#!/usr/bin/env python3
"""Запуск последнего записанного теста"""
import sys
import subprocess
from pathlib import Path

tests_dir = Path("recorded_tests")
tests = sorted(tests_dir.glob("*.py"), key=lambda x: x.stat().st_mtime, reverse=True)

if not tests:
    print("❌ No tests found in recorded_tests/")
    sys.exit(1)

latest = tests[0]
print(f"▶️  Running: {latest.name}")
print(f"📅 Created: {latest.stat().st_mtime}")
print("-" * 60)

result = subprocess.run([sys.executable, str(latest)])
sys.exit(result.returncode)

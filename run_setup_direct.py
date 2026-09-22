#!/usr/bin/env python3
import subprocess
import sys

# Run setup.py directly
result = subprocess.run([sys.executable, "setup.py"], capture_output=True, text=True)
print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr)
sys.exit(result.returncode)
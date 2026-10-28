import os, sys, subprocess

# Test 1: Run from repo root
p1 = subprocess.run([sys.executable, "-c", "import app.main; print('Repo root import: OK')"], cwd="d:/exasol", capture_output=True, text=True)
print(p1.stdout or p1.stderr)

# Test 2: Run from inside app directory
p2 = subprocess.run([sys.executable, "-c", "import main; print('App dir import: OK')"], cwd="d:/exasol/app", capture_output=True, text=True)
print(p2.stdout or p2.stderr)

# Test 3: Run streamlit with no app in sys.path
p3 = subprocess.run([sys.executable, "-c", "import sys; sys.path = [p for p in sys.path if 'exasol' not in p.lower()]; import app.main; print('Clean path import: OK')"], cwd="d:/exasol", capture_output=True, text=True)
print(p3.stdout or p3.stderr)

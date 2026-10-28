import subprocess
import time
import urllib.request
import sys

proc = subprocess.Popen([
    sys.executable, "-m", "streamlit", "run", "app/main.py",
    "--server.port", "8501",
    "--server.headless", "true"
])
print("Streamlit launched with PID:", proc.pid)
time.sleep(5)
try:
    with urllib.request.urlopen("http://127.0.0.1:8501", timeout=5) as resp:
        print("HTTP Status Code:", resp.getcode())
        print("SUCCESS: Streamlit server is active and serving requests!")
except Exception as e:
    print("Error connecting:", e)
finally:
    proc.terminate()
    proc.wait()
    print("Streamlit terminated cleanly.")

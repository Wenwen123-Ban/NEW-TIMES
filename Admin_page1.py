"""
LBAS Smart Launcher — Admin_page1.py
Double-click the .bat or run this file directly.
Starts Django + opens browser automatically.
"""
import os
import sys
import subprocess
import webbrowser
import time
import socket

HOST = "0.0.0.0"
PORT = 5000
BROWSER_URL = f"http://localhost:{PORT}/admin"

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    manage_py = os.path.join(base_dir, "manage.py")

    if not os.path.exists(manage_py):
        print("[LBAS] ERROR: manage.py not found. Run Django setup first.")
        input("Press Enter to exit...")
        sys.exit(1)

    os.chdir(base_dir)

    print("[LBAS] Checking database migrations...")
    subprocess.run(
        [sys.executable, "manage.py", "migrate", "--run-syncdb"],
        cwd=base_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    print(f"[LBAS] Starting server on port {PORT}...")

    try:
        import waitress  # noqa: F401
        server_cmd = [
            sys.executable, "-c",
            f"import waitress; from lbas_project.wsgi import application; "
            f"waitress.serve(application, host='{HOST}', port={PORT})"
        ]
    except ImportError:
        server_cmd = [sys.executable, "manage.py", "runserver", f"{HOST}:{PORT}", "--noreload"]

    server_proc = subprocess.Popen(server_cmd, cwd=base_dir)

    print("[LBAS] Waiting for server to start...")
    for _ in range(20):
        time.sleep(0.5)
        if is_port_in_use(PORT):
            break

    print(f"[LBAS] Opening browser: {BROWSER_URL}")
    webbrowser.open(BROWSER_URL)
    print("[LBAS] Server running. Close this window to stop.")

    try:
        server_proc.wait()
    except KeyboardInterrupt:
        server_proc.terminate()
        print("[LBAS] Server stopped.")

if __name__ == "__main__":
    main()

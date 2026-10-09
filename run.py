"""Start the web application:   python run.py

Configuration comes from environment variables. For convenience, a file
named .env in this folder (KEY=value per line, see .env.example) is read
first; real environment variables take precedence. The .env file is
listed in .gitignore so passwords are never committed.
"""
import os
from pathlib import Path


def load_env_file(path):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


load_env_file(Path(__file__).with_name(".env"))

from app import create_app  # noqa: E402  (must run after the .env file is loaded)

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    print(f"Open http://127.0.0.1:{port} in your browser (Ctrl+C to stop).")
    app.run(host="127.0.0.1", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")

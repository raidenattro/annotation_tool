import threading
import time
import webbrowser

from app import app


def open_browser_later(url):
    # Delay avoids race where browser opens before Flask starts listening.
    time.sleep(1.0)
    webbrowser.open(url)


if __name__ == "__main__":
    url = "http://127.0.0.1:5000"
    threading.Thread(target=open_browser_later, args=(url,), daemon=True).start()
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)

import signal, os
from multiprocessing.connection import Listener
from concurrent.futures import ThreadPoolExecutor
from basalt.core import make_flashcard
from appdirs import user_cache_dir

executor = ThreadPoolExecutor(max_workers=10)

SOCKET_PATH = os.path.join(user_cache_dir("basalt"), "daemon.sock")

if os.path.exists(SOCKET_PATH):
    os.remove(SOCKET_PATH)

running = True

def stop(*args):
    global running
    running = False

signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGTERM, stop)

with Listener(str(SOCKET_PATH), authkey=b"basalt") as srv:
    while running:
        try:
            conn = srv.accept()
            data = conn.recv()
            content, user_inputs, configs = data["content"], data["user_inputs"], data["configs"]
            executor.submit(make_flashcard, content, user_inputs, configs)
            conn.close()
        except Exception:
            pass  # You could log this
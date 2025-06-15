import signal, os
from multiprocessing.connection import Listener
from concurrent.futures import ThreadPoolExecutor
from basalt.core import make_flashcard
from appdirs import user_cache_dir

executor = ThreadPoolExecutor(max_workers=10)

SOCKET_PATH = os.path.join(user_cache_dir("basalt"), "daemon.sock")

os.makedirs(os.path.dirname(SOCKET_PATH), exist_ok=True)
if os.path.exists(SOCKET_PATH):
    os.remove(SOCKET_PATH)

running = True

def stop(*args):
    global running
    running = False

signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGTERM, stop)


def safe_make_flashcard(x, y, z):
    try:
        make_flashcard(x, y, z)
    except Exception as e:
        print("Exception in flashcard thread:", e)
        os._exit(1)


with Listener(str(SOCKET_PATH), authkey=b"basalt") as srv:
    while running:
        try:
            conn = srv.accept()
            data = conn.recv()
            content, user_inputs, configs = data["content"], data["user_inputs"], data["configs"]
            executor.submit(safe_make_flashcard, content, user_inputs, configs)
            print(f"daemon has submitted job")
            conn.close()
        except Exception as e:
            raise e
    print("Shutting down... waiting for in-progress jobs.")
    executor.shutdown(wait=True)
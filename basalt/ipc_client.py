from multiprocessing.connection import Client
from appdirs import user_cache_dir
import os

SOCKET_PATH = os.path.join(user_cache_dir("basalt"), "config.json")

def send_job(job_dict):
    with Client(str(SOCKET_PATH), authkey=b"basalt") as c:
        c.send(job_dict)

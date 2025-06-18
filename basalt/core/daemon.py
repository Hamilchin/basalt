"""Basalt background daemon.

Listens on a UNIX-domain socket for flash‑card creation requests and hands the
work off to a thread‑pool.  Terminates cleanly on SIGINT/SIGTERM.
"""
from concurrent.futures import ThreadPoolExecutor
from multiprocessing.connection import Listener
import logging, os, signal

from appdirs import user_cache_dir
from basalt.core.core import make_flashcard

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def socket_path() -> str:
    return os.path.join(user_cache_dir("basalt"), "daemon.sock")

def _submit_job(executor: ThreadPoolExecutor, data: dict) -> None:
    #exceptions in job do not kill listener

    content, data, configs = data["content"], data["user_inputs"], data["configs"]

    logging.info("submitting job with content: %s", content if len(content) < 20 else content[:20])

    fut = executor.submit(
        make_flashcard, content, data, configs
    )

    def _log_failure(fut):
        if fut.exception():
            logging.exception("flashcard job failed", exc_info=fut.exception())

    fut.add_done_callback(_log_failure)


def start_daemon(max_workers: int = 10) -> None:

    path = socket_path()

    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    except FileNotFoundError:
        os.remove(path)

    with (Listener(str(path), authkey=b"basalt") as srv,
        ThreadPoolExecutor(max_workers=max_workers) as executor):
        #only blocking part is when executor exits; waits for all threads to finish. 


        def _stop(*_):
            logging.info("shutdown requested; (any blocking here is from waiting for thread finish)")
            srv.close()  # causes srv.accept() to raise and break the loop

        signal.signal(signal.SIGINT, _stop)
        signal.signal(signal.SIGTERM, _stop)

        logging.info("listener running on %s", path)

        while True:
            try:
                conn = srv.accept()
            except OSError:
                logging.info("shutdown requested")
                break


            with conn:
                try:
                    _submit_job(executor, conn.recv())
                except Exception: #sync errors; async errors in child thread are caught with _log_failure
                    logging.exception("invalid client payload")

    logging.info("daemon exiting")


if __name__ == "__main__":
    start_daemon()
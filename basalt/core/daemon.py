"""Basalt background daemon.

Listens on a UNIX-domain socket for flash‑card creation requests and hands the
work off to a thread‑pool.  Terminates cleanly on SIGINT/SIGTERM.
"""
import logging, os, signal, json
from concurrent.futures import ThreadPoolExecutor
from multiprocessing.connection import Listener
from appdirs import user_cache_dir

from basalt.core.llm import call_model
from basalt.core.database import FlashcardDB
from basalt.core.config import get_db_path


#============= MAKE FLASHCARD HELPERS =================

def create_prompt(custom_prompt, custom_commands, user_inputs):

    system_prompt = f"""
        You are a flashcard generator for a spaced repetition app. 

        Given this piece of text, extract a key idea (or ideas) that would help the user learn and remember the knowledge contained in the text. Assume they've read the text already; your aim should be to jog their mind, and do not over-explain. Represent each as a flashcard object in JSON format with "question" and "answer" fields, and possibly more, if the user specifies. Return a single JSON array of such flashcards. 
        
        Use clear, concise phrasing. Each fact should form its own flashcard. 
        Only output valid JSON; no other text. 

    """

    user_prompt = ""
    
    if custom_prompt.strip() or (len(user_inputs) != 0): #is this necessary? 
        user_prompt += "Here are the user's custom instructions: \n"
    
    user_prompt += custom_prompt

    for flag, input in user_inputs.items():
        user_prompt += " "
        assert type(input) == str
        if input == True:
            user_prompt += custom_commands[flag]
        else:
            user_prompt += custom_commands[input].replace("{}", str(input))

    prompt = system_prompt + user_prompt

    return prompt


def extract_json_array(text):

    start, end = text.find('['), text.rfind(']')
    if start == -1 or end == -1:
        raise ValueError("Not wrapped correctly in square brackets")
    
    return json.loads(text[start : end + 1])


def make_flashcard(content, user_inputs, configs):

    logging.debug("make_flashcard called")

    if not content or not configs:
        raise ValueError(f"No {"configs" if not configs else "content"} passed to make_flashcard! (this should never happen)")

    prompt = create_prompt(configs["custom_prompt"], configs["custom_commands"], user_inputs)

    text_resp = call_model(prompt, content, configs)

    try:
        flashcards = extract_json_array(text_resp)
    except Exception as e:
        return None

    with FlashcardDB(get_db_path()) as database:
        logging.debug("storing batch from core")
        database.store_batch(flashcards, content)
    
    logging.debug("make_flashcard finished from core")

#============= MAKE FLASHCARD =================

def socket_path() -> str:
    return os.path.join(user_cache_dir("basalt"), "daemon.sock")

def _submit_job(executor: ThreadPoolExecutor, data: dict) -> None:
    #exceptions in job do not kill listener

    content, data, configs = data["content"], data["user_inputs"], data["configs"]

    logging.info("submitting job with content: %s ...", content if len(content) < 40 else content[:40])

    fut = executor.submit(
        make_flashcard, content, data, configs
    )

    def _log_done(fut):
        if fut.exception():
            logging.exception("flashcard job failed", exc_info=fut.exception())
        else:
            logging.info("Flashcard batch finished")

    fut.add_done_callback(_log_done)


def start_daemon(max_workers: int = 10) -> None:

    path = socket_path()

    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        os.remove(path)
    
    executor = ThreadPoolExecutor(max_workers=max_workers)
    srv = Listener(str(path), authkey=b"basalt")

    def _stop(*_):
        logging.info("Force shutdown requested")
        srv.close()
        executor.shutdown(wait=False)

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    logging.info("Daemon started with PID %d", os.getpid())
    logging.info("listener running on %s", path)

    try:
        while True:
            try:
                conn = srv.accept()
            except OSError:
                logging.info("shutdown requested")
                break

            try:
                _submit_job(executor, conn.recv())
            except Exception:
                logging.exception("invalid client payload")
    finally:
        logging.info("daemon exiting")
        srv.close()

if __name__ == "__main__":
    start_daemon()
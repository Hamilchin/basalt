"""Basalt background daemon.

Listens on a UNIX-domain socket for flash‑card creation requests and hands the
work off to a thread‑pool.  Terminates cleanly on SIGINT/SIGTERM.
"""
import logging, os, signal, json
from concurrent.futures import ThreadPoolExecutor
from multiprocessing.connection import Listener
from appdirs import user_cache_dir

from basalt.core.api_calls import call_model, get_youtube_transcript
from basalt.core.database import FlashcardDB
from basalt.core.config import db_path, socket_path


logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s"
)
logger.setLevel(logging.INFO)



# ==== THREAD JOBS =======

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

def make_flashcard(content, user_inputs, configs):

    logger.debug("make_flashcard called")

    if not content or not configs:
        raise ValueError(f"No {"configs" if not configs else "content"} passed to make_flashcard! (this should never happen)")

    prompt = create_prompt(configs["custom_prompt"], configs["custom_commands"], user_inputs)

    text_resp = call_model(prompt, content, configs)


    start, end = text_resp.find('['), text_resp.rfind(']')
    if start == -1 or end == -1:
        raise ValueError("Not wrapped correctly in square brackets")
    
    flashcards = json.loads(text_resp[start : end + 1])


    with FlashcardDB(db_path()) as database:
        logger.debug("storing batch from core")
        database.store_batch(flashcards, content)
    
    logger.debug("make_flashcard finished from core")

def _transcribe_then_flashcard(url, user_inputs, configs):
    text = get_youtube_transcript(url)
    make_flashcard(text, user_inputs, configs)

# =========== (thread jobs ^) ======== 

# ==== DAEMON =======

def start_daemon(max_workers: int = 10) -> None:

    path = socket_path()

    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        os.remove(path)
    
    executor = ThreadPoolExecutor(max_workers=max_workers)
    srv = Listener(str(path), authkey=b"basalt")

    def _stop(*_):
        logger.info("Force shutdown requested")
        srv.close()
        executor.shutdown(wait=False)

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    logger.info("Daemon started with PID %d", os.getpid())
    logger.info("listener running on %s", path)

    try:
        while True:
            try:
                conn = srv.accept()
            except OSError:
                logger.info("shutdown requested")
                break

            try:
                data = conn.recv()

                # === job submit handling === 
                kind = data.get("kind")
                if kind == "url":
                    fut = executor.submit(
                        _transcribe_then_flashcard,
                        data["url"],
                        data["user_inputs"],
                        data["configs"],
                    )
                else:
                    fut = executor.submit(
                        make_flashcard,
                        data["content"],
                        data["user_inputs"],
                        data["configs"],
                    )

                fut.add_done_callback(
                    lambda f: logger.exception("job failed", exc_info=f.exception())
                    if f.exception()
                    else logger.info("job finished"),
                )
                # === job submit handling ^^^ === 

            except Exception:
                logger.exception("invalid client payload")
    finally:
        logger.info("daemon exiting")
        srv.close()

if __name__ == "__main__":
    start_daemon()
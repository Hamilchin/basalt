from basalt.core.config import get_configs, set_config
from basalt.core.core import display_tree
from basalt.core.wipe import clear_cache, clear_configs, clear_db
from basalt.core.daemon import start_daemon, socket_path
from basalt.core.database import FlashcardDB
from multiprocessing.connection import Client
from pyperclip import paste
from pynput import keyboard
import fire, sys, json, os

def set(config_name, new_value):
    configs = get_configs
    if config_name not in configs: 
        raise ValueError(f"'{config_name}' is not a valid config")
    set_config(config_name, new_value)

def capture(input=None, file_path=None, **user_inputs):
    configs = get_configs()
    custom_commands = configs["custom_commands"]

    valid_inputs = {key: value for key, value in user_inputs.items() if key in custom_commands}

    if len(valid_inputs) < len(user_inputs):
        invalid_flags = [key for key in user_inputs if key not in custom_commands]
        raise ValueError(f"unrecognized flags: {', '.join(invalid_flags)}")

    if input == "file":
        if not file_path: 
            raise ValueError("no file path provided")
        else:
            try: 
                with open(file_path, "r", encoding="utf-8") as file:
                    content = file.read()
            except:
                raise FileNotFoundError("file does not exist or cannot be read")

    elif input == "clip" or not input:
        try:
            content = paste()
            if not content.strip():
                raise ValueError("Clipboard is empty")
        except:
            raise RuntimeError("clipboard could not be accessed")

    else:
        content = input
        if not content.strip():
            raise ValueError("No text provided")

    def send_job(job_dict):
        with Client(str(socket_path()), authkey=b"basalt") as c:
            c.send(job_dict)

    send_job(
        {"content" : content, 
         "user_inputs" : user_inputs, 
         "configs": configs}
        )
    
def reset(*targets, quiet: bool = False):
    """
    Reset Basalt state.

    USAGE
    -----
    ▶ basalt reset
          → wipe db, cache, and configs
    ▶ basalt reset cache configs
          → wipe only cache and configs

    Positional *targets can be any of {"db", "cache", "configs"}.
    If none are provided, all three are selected.
    """
    valid = {"db", "cache", "configs"}

    if targets:
        invalid = [t for t in targets if t not in valid]
        if invalid:
            raise ValueError(f"Unknown target(s): {', '.join(invalid)}")
        chosen = targets
    else:
        chosen = valid

    if not quiet:
        confirm = input(
            f"⚠  This will delete {', '.join(sorted(chosen))}. Continue? [y/N]: "
        ).lower()
        if confirm not in {"y", "yes"}:
            print("Reset aborted.")
            return

    if "db" in chosen:
        clear_db()
    if "cache" in chosen:
        clear_cache()
    if "configs" in chosen:
        clear_configs()


def dev(clean: bool = True):
    if clean:
        clear_db()
        clear_cache()
    start_daemon()

def inbox():
    configs = get_configs()
    db_path = os.path.join(configs["data_dir"], "flashcard_data.db")
    with FlashcardDB(db_path) as db:
        while True:
            current_cards = db.get_due_cards()

            if current_cards: 
                current_card = current_cards.pop(0)
                id, folder_id, batch_id, question, answer, other_data, rep_data, next_due, created_at = current_card["id"], current_card["folder_id"], current_card["batch_id"], current_card["question"], current_card["answer"], current_card["other_data"], current_card["rep_data"], current_card["next_due"], current_card["created_at"]

                current_folder = db.get_folder(folder_id)
                current_batch = db.get_batch(batch_id)

                print(f"folder: {current_folder["folder_name"]} | inbox: {len(current_cards)} remaining")
                print(f"QUESTION: {question}" )
                print(f"ANSWER: {answer}")
        

#========== UNIVERSAL UTILITY FUNCTIONS ===========

def 

# id         INTEGER PRIMARY KEY,
#         folder_id    INTEGER NOT NULL DEFAULT {ROOT_FOLDER_DEFAULTS['id']},
#         batch_id   INTEGER, 

#         question   TEXT NOT NULL,
#         answer     TEXT NOT NULL,
#         other_data      JSON,

#         rep_data      JSON,
#         next_due      TIMESTAMP,
#         created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

#         FOREIGN

COMMANDS_DICT = {
    "set": set,
    "list": list,
    "capture": capture,
    "reset": reset,
    "dev" : dev
}

def run_command(argv=None):
    if not argv:
        argv = sys.argv[1:]

    new_argv = []
    for arg in argv: #hacky stuff for fire
        if arg.startswith("-") and not arg.startswith("--"):
            if len(arg) == 2:
                new_argv.append(f"--{arg[1:]}")
            else:  # bundled: -not -> --n --o --t
                new_argv.extend(f"--{c}" for c in arg[1:])
        else:
            new_argv.append(arg)

    fire.Fire(COMMANDS_DICT, command=new_argv)
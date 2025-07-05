from basalt.core.config import get_configs, set_config as base_set_config, db_path, default_configs
from basalt.core.config import socket_path
from basalt.core.database import FlashcardDB, ROOT_FOLDER_DEFAULTS, DEFAULT_FOLDER_SETTINGS
from basalt.core.spaced_repetition import get_interval_sm2
from basalt.core.datetime_utils import now_dt, dt_to_sql_timestamp, sql_timestamp_to_dt

from multiprocessing.connection import Client
from appdirs import user_cache_dir, user_config_dir
from pyperclip import paste

import os, logging, shutil, datetime, fire

logger = logging.getLogger(__name__)

# all higher-level basalt error handling is in here. lower-level (i.e. get errors) are in database.py
# should only allow valid operations on basalt state. 
# the functions have direct access to the database and configs and things; nothing passed in.
# all of this is client-side code.
#these functions are wrapped in CLI and GUI, but some have CLI-like inputs for hotkey ease. 
    #most of them are just for reusable utils

#================== HELPERS ===================

def parse_argv(argv): #changes argv to accept single-dash flag params
    new_argv = []
    for arg in argv: #hacky stuff for fire
        if arg.startswith("-") and not arg.startswith("--"):
            if len(arg) == 2:
                new_argv.append(f"--{arg[1:]}")
            else:  # bundled: -not -> --n --o --t
                new_argv.extend(f"--{c}" for c in arg[1:])
        else:
            new_argv.append(arg)
    return new_argv

def assert_valid_config_edit(path: str, value) -> None:
    default = default_configs()
    parts = path.split(".")
    key = parts[0]
    if key not in default:
        raise ValueError(f"Config type unrecognized: {key}")
    if key == "custom_commands" or key == "hotkeys":
        if len(parts) != 2 or not isinstance(value, str):
            raise ValueError(f"Invalid type or invalid edit")
        return
    if len(parts) != 1:
        raise ValueError(f"Invalid config edit path: {path}")

    elif not isinstance(value, type(default[key])):
        raise ValueError(f"Invalid config value type for {key}: {value, type(value)}")

def assert_valid_folder_edit(folder_id: int, edit_path: str, new_value) -> None:
    with FlashcardDB(db_path()) as db:
        db.get_folder(folder_id)
    parts = edit_path.split(".")
    if parts[0] == "parent_id" and len(parts) == 1:
        if not isinstance(new_value, int):
            raise ValueError("parent_id must be an integer")
        with FlashcardDB(db_path()) as db:
            try:
                db.get_folder(new_value)
            except Exception:
                raise ValueError(f"Parent folder not found: {new_value}")
            # ensure no cycles
            tree = db.get_folder_tree(folder_id)
            def collect_ids(t):
                ids = [t["id"]]
                for c in t["children"]:
                    ids.extend(collect_ids(c))
                return ids
            if new_value in collect_ids(tree):
                raise ValueError("Cannot set parent_id to a descendant (cycle)")
        return
    if parts[0] == "name" and len(parts) == 1:
        if not isinstance(new_value, str):
            raise ValueError("Folder name must be a string")
        return
    if parts[0] == "folder_settings":
        setting = DEFAULT_FOLDER_SETTINGS
        for p in parts[1:]:
            if isinstance(setting, dict) and p in setting:
                setting = setting[p]
            else:
                raise ValueError(f"Invalid folder_settings path: {edit_path}")
        if not isinstance(new_value, type(setting)):
            raise ValueError(f"Invalid type for {edit_path}: {new_value, type(new_value)}")
        return
    raise ValueError(f"Invalid folder edit path: {edit_path}")

def assert_valid_flashcard_edit(card_id: int, edit_path: str, new_value) -> None:
    if edit_path in ("question", "answer") or edit_path.startswith("other_data."):
        if not isinstance(new_value, str):
            raise ValueError(f"{edit_path} must be a string")
        return
    raise ValueError(f"Invalid flashcard edit path: {edit_path}")

#==== USABLE INSIDE OF CUSTOM HOTKEY COMMANDS ======

def set_config(path: str, value):
    assert_valid_config_edit(path, value)
    base_set_config(path, value)

def set_folder(folder_id: int, edit_path: str, new_value):
    assert_valid_folder_edit(folder_id, edit_path, new_value)
    with FlashcardDB(db_path()) as db:
        if edit_path == "name":
            db.update_folder_fields(folder_id, {"name": new_value})
        elif edit_path == "parent_id":
            db.update_folder_fields(folder_id, {"parent_id": new_value})
        else:
            folder = db.get_folder(folder_id)
            settings = folder["folder_settings"]
            parts = edit_path.split(".")[1:]
            node = settings
            for p in parts[:-1]:
                node = node[p]
            node[parts[-1]] = new_value
            db.update_folder_fields(folder_id, {"folder_settings": settings})

def set_flashcard(flashcard_id: int, edit_path: str, new_value):
    assert_valid_flashcard_edit(flashcard_id, edit_path, new_value)
    with FlashcardDB(db_path()) as db:
        if edit_path in ("question", "answer", "folder_id"):
            db.update_flashcard_fields(flashcard_id, {edit_path: new_value})
        else:
            card = db.get_card(flashcard_id)
            other = card.get("other_data") or {}
            key = edit_path.split(".", 1)[1]
            other[key] = new_value
            db.update_flashcard_fields(flashcard_id, {"other_data": other})

def set(target: str, identifier: str, edit_path_or_new_value: str, new_value):
    """
    Generic setter for 'config', 'folder', or 'card'.
    - For 'config': identifier is the config path, e.g. "custom_commands.d".
    - For 'folder': identifier is the folder name; for parent_id edits, new_value is the parent folder name.
    - For 'card': identifier is the card ID (string or int).
    """
    target = target.lower()
    if target == "config":
        set_config(identifier, new_value)

    elif target == "folder":
        with FlashcardDB(db_path()) as db:
            if edit_path_or_new_value == "parent":
                new_value = db.get_folder_id_from_name(new_value)
                edit_path_or_new_value = "parent_id"

            folder_id = db.get_folder_id_from_name(identifier)
            set_folder(folder_id, edit_path_or_new_value, new_value)

    elif target in ("card", "flashcard"):
        set_flashcard(int(identifier), edit_path_or_new_value, new_value)

    else:
        raise ValueError(f"Unknown target: {target}")

def review_flashcard(flashcard_id, score:int): #to avoid double-reviewing at start, call after every flashcard init with score=5. 
    with FlashcardDB(db_path()) as database:
        flashcard = database.get_card(flashcard_id)
        if flashcard: 

            rep_settings = database.get_folder_settings(flashcard["folder_id"])
            history = flashcard["rep_data"]["history"]
            now = now_dt()
            history.append((score, dt_to_sql_timestamp(now)))
            database.update_flashcard_fields(flashcard_id, {"rep_data": flashcard["rep_data"]})
            #rep_data has been mutated
            
            if rep_settings["algorithm"] == "sm2":
                sm2_settings = rep_settings["sm2_settings"]
                interval = get_interval_sm2(history, sm2_settings) #in hours
                next_due = now + datetime.timedelta(hours=interval)
                sql_next_due = dt_to_sql_timestamp(next_due)
                database.update_flashcard_fields(flashcard_id, {"next_due": sql_next_due})
            else:
                raise NotImplementedError(f"Other spaced repetition algorithm {rep_settings["algorithm"]} not supported yet!")

        else:
            raise ValueError(f"Missing flashcard requested to update: id {flashcard_id}")

def capture(input=None, file_path_or_url=None, **user_inputs): #user_inputs is where custom LLM prompts get put

    if input == "file":
        kind = "file"
        if not file_path_or_url: 
            raise ValueError("no file path provided")
        else:
            try: 
                with open(file_path_or_url, "r", encoding="utf-8") as file:
                    content = file.read()
            except:
                raise FileNotFoundError("file does not exist or cannot be read")

    elif input == "clip" or not input:
        kind = "clip"
        try:
            content = paste()
            if not content.strip():
                raise ValueError("Clipboard is empty")
        except:
            raise RuntimeError("clipboard could not be accessed")
        
    elif input == "url":
        kind = "url"
        if not file_path_or_url: 
            raise ValueError("no file path provided")
        else:
            try:
                with open(file_path_or_url, "r", encoding="utf-8") as file:
                    content = file.read()
            except:
                raise FileNotFoundError("file does not exist or cannot be read")

    else:
        content = input
        kind = "raw"
        if not content.strip():
            raise ValueError("No text provided")

    def send_job(job_dict):
        with Client(str(socket_path()), authkey=b"basalt") as c:
            c.send(job_dict)

    configs = get_configs()
    custom_commands = configs["custom_commands"]

    valid_inputs = {key: value for key, value in user_inputs.items() if key in custom_commands}

    if len(valid_inputs) < len(user_inputs):
        invalid_flags = [key for key in user_inputs if key not in custom_commands]
        raise ValueError(f"unrecognized flags: {', '.join(invalid_flags)}")

    send_job(
        {
         "kind" : kind,
         "content" : content,
         "user_inputs" : user_inputs, 
         "configs": configs
        }
    )

#all return whether or not something was removed
def clear_db():
    configs = get_configs()
    db_path = os.path.join(configs["data_dir"], "flashcard_data.db")
    if os.path.exists(db_path):
        os.remove(db_path)
        return True
    return False

def clear_cache():
    cache_path = user_cache_dir("basalt")
    if os.path.exists(cache_path):
        shutil.rmtree(cache_path)
        return True
    return False

def clear_configs():
    config_dir = user_config_dir("basalt")
    if os.path.exists(config_dir):
        shutil.rmtree(config_dir)
        return True
    return False

from basalt.core.config import get_configs, set_config
from basalt.core.daemon import start_daemon, socket_path
from basalt.core.database import FlashcardDB
from basalt.core.spaced_repetition import review_flashcard
from multiprocessing.connection import Client
from pyperclip import paste
from pynput import keyboard
import fire, sys, os



def move_flashcard_to_folder_name(flashcard_id, folder_name):
    with FlashcardDB(get_db_path()) as db:
        folder_id = db.get_folder_id_from_name(folder_name)
        db.update_flashcard_fields(flashcard_id, {"folder_id": folder_id})


def clear_db():
    """
    Delete the flashcard database defined in the current Basalt configs.
    """
    configs = get_configs()
    db_path = os.path.join(configs["data_dir"], "flashcard_data.db")
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"Deleted DB at: {db_path}")
    else:
        print("No DB file found to delete.")

def clear_cache():
    """
    Remove Basalt's cache directory (found via appdirs).
    """
    cache_path = user_cache_dir("basalt")
    if os.path.exists(cache_path):
        shutil.rmtree(cache_path)
        print(f"Deleted cache at: {cache_path}")
    else:
        print("No cache directory found.")

def clear_configs():
    """
    Remove the user-specific Basalt configuration directory so that default
    configs are regenerated on the next run.
    """
    config_dir = user_config_dir("basalt")
    if os.path.exists(config_dir):
        shutil.rmtree(config_dir)
        print(f"Deleted configs at: {config_dir}")
    else:
        print("No configs directory found.")

#FUNCTIONS TO INTERACT WITH BASALT; I.E. ONES THAT MAY BE CALLED THROUGH HOTKEYS
#AND ONES THAT ARE CALLED IN BOTH CLI AND MacOS GUI. 
#THESE RAISE NORMAL ERRORS; MUST CATCH IF YOU WANT DIFFERENT ERROR BEHAVior
#none of these return anything. They are meant to be called in a "command line style" way. 

def set(config_name, new_value): #TODO: ADD MORE SPECIFIC ERROR HANDLING
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


def dev(clean=False):
    if clean:
        clear_db()
        clear_cache()
    start_daemon()


COMMANDS_DICT = {
    "set": set,
    "capture": capture,
    "reset": reset,
    "dev" : dev
}

#========================================================================

def parse_argv(argv=None):
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

def run_command(argv):
    fire.Fire(COMMANDS_DICT, command=argv)
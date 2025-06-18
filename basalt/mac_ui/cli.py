
from basalt.core.command_utils import run_command
from basalt.core.config import get_configs, set_config
from basalt.core.core import display_tree
from basalt.core.wipe import clear_cache, clear_configs, clear_db
from basalt.core.daemon import start_daemon, socket_path
from basalt.core.database import FlashcardDB
from multiprocessing.connection import Client
from pyperclip import paste
from pynput import keyboard
import fire, sys, json, os

def set(config_name, new_value=None):
    if config_name == "hotkey":
        hk_string = input("Enter your desired hotkey combination. <cmd>+<shift>+<alt>+<space>+b: ")
        hk_string = hk_string.strip()
        try: keyboard.HotKey.parse(hk_string) 
        except:
            print(f"Error: '{hk_string}' is not a valid path", file=sys.stderr); 
            sys.exit(1)
        new_value = hk_string
    run_command()

def list(to_list="", folder_name=None):
    to_list = to_list.strip()
    if to_list not in ("config", "configs", "cards", "folder", ""):
        print(f"Error: '{to_list}' not recognizable"); 
        sys.exit(1)
    elif to_list in ("config", "configs"):
        print(json.dumps(get_configs(), indent=2))
    elif to_list in ("cards", "folder", ""):
        if not folder_name:
            display_tree(get_configs())
        else:
            display_tree(get_configs(), folder_name)

def capture(input=None, file_path=None, **user_inputs):
    configs = get_configs()
    custom_commands = configs["custom_commands"]

    valid_inputs = {key: value for key, value in user_inputs.items() if key in custom_commands}

    if len(valid_inputs) < len(user_inputs):
        invalid_flags = [key for key in user_inputs if key not in custom_commands]
        print(f"Error: unrecognized flags: {', '.join(invalid_flags)}", file=sys.stderr)
        sys.exit(1)

    if input == "file":
        if not file_path: 
            print(f"Error: no file path provided", file=sys.stderr)
            sys.exit(1)
        else:
            try: 
                with open(file_path, "r", encoding="utf-8") as file:
                    content = file.read()
            except:
                print(f"Error: file does not exist or cannot be read", file=sys.stderr)
                sys.exit(1)

    elif input == "clip" or not input:
        try:
            content = paste()
            if not content.strip():
                print("Clipboard is empty", file=sys.stderr)
                sys.exit(1)
        except:
            print("Error: clipboard could not be accessed", file=sys.stderr)
            sys.exit(1)

    else:
        content = input
        if not content.strip():
            print("No text provided", file=sys.stderr)
            sys.exit(1)

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
            print(f"Unknown target(s): {', '.join(invalid)}", file=sys.stderr)
            return
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

if __name__ == "__main__":
    run_command()
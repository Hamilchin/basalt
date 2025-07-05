from basalt.core.config import get_configs, db_path
from basalt.core.database import FlashcardDB, ROOT_FOLDER_DEFAULTS
from basalt.core.daemon import start_daemon
from basalt.core.core_commands import (parse_argv, clear_cache, clear_db, clear_configs,  ) 

from basalt.core.core_commands import set as core_set, capture as core_capture, reset as core_reset
import fire, sys, json, os, logging

def print_db():
    with FlashcardDB(db_path()) as conn: 
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]

        for table in tables:
            print(f"\n=== {table.upper()} ===")
            cursor.execute(f"PRAGMA table_info({table})")
            cols = [col[1] for col in cursor.fetchall()]
            print(" | ".join(cols))
            print("-" * (len(" | ".join(cols))))

            cursor.execute(f"SELECT * FROM {table}")
            for row in cursor.fetchall():
                print(" | ".join(str(x) for x in row))



logging.basicConfig(
    level=logging.DEBUG, 
    format="%(levelname)s: %(filename)s, line %(lineno)d: %(message)s"
)

class CLI:
    def __init__(self):
        self.configs = get_configs()
        self.db_path = get_db_path()

    def set(self, config_name: str, new_value):
        try:
            core_set(config_name, new_value)
        except Exception as e:
            print(f"Error: {e}")

    def capture(self, input=None, file_path=None, **user_inputs):
        try:
            core_capture(input=input, file_path=file_path, **user_inputs)
        except Exception as e:
            print(f"Error: {e}")

        
    def reset(self, *targets, quiet: bool = False):
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

    def dev(self, clean: bool = False):
        try: 
            if clean:
                clear_db()
                clear_cache()
            start_daemon()
        except Exception as e:
            print(f"Error: {e}")

    def list(self, to_list="", target=None):
        to_list = to_list.strip()
        if to_list not in ("config", "configs", "cards", "folder", "all", "folders", ""):
            raise ValueError("to_list not recognizable")
        elif to_list in ("config", "configs"):
            if not target:
                print(json.dumps(self.configs, indent=2))
            else:
                print(json.dumps(self.configs[target], indent=2))
        elif to_list in ("cards", "folder", "folders", ""):
            if not target:
                self.display_tree()
            else:
                self.display_tree(target)
        elif to_list in ("all"):
            with FlashcardDB(self.db_path) as db:
                db.print_db()


    def display_tree(self, id=ROOT_FOLDER_DEFAULTS["id"]):
        with FlashcardDB(self.db_path) as database:
            self.print_folder_tree(database.get_folder_tree(id))

    def print_folder_tree(self, tree, indent=2):
        """Recursively pretty-print a folder tree structure."""
        prefix = "    " * indent + ("├── " if indent else "")
        print(f"{prefix}{tree['name']} (id: {tree['id']})")
        for card_id in tree["cards"]:
            print("    " * (indent + 1) + f"- card {card_id}")
        for child in tree["children"]:
            self.print_folder_tree(child, indent + 1)


    def inbox(self):
        with FlashcardDB(self.db_path) as db:
            while True:
                current_cards = db.get_due_cards()

                if not current_cards:
                    print("No due cards. ")
                    break
            
                current_card = current_cards.pop(0)
                id, folder_id, batch_id, question, answer, other_data, rep_data, next_due, created_at = current_card["id"], current_card["folder_id"], current_card["batch_id"], current_card["question"], current_card["answer"], current_card["other_data"], current_card["rep_data"], current_card["next_due"], current_card["created_at"]

                current_folder = db.get_folder(folder_id)
                current_batch = db.get_batch(batch_id)

                print(f"folder: {current_folder['name']} | inbox: {len(current_cards)} remaining")
                print(f"QUESTION: {question}" )
                print(f"ANSWER: {answer}")
                if other_data:
                    print(f"{other_data}")

                finished = False

                while not finished:

                    cmd = None
                    while not cmd:
                        try:
                            cmd = self.parse_inbox_cmd(input())
                        except ValueError as e:
                            print(f"Error: {e}")
                            pass
                    
                    if cmd[0] == "rate":
                        review_flashcard(id, cmd[1])
                        finished = True

                    elif cmd[0] == "delete":
                        db.delete_flashcard(id)
                        finished = True

                    elif cmd[0] == "edit":
                        if cmd[1] in ("question", "answer"):
                            db.update_flashcard_fields(id, {cmd[1]: cmd[2]})
                        else:
                            other_data[cmd[1]] = cmd[2]
                            db.update_flashcard_fields(id, {"other_data" : other_data})
                        finished = True

                    elif cmd[0] == "move":
                        folder_name = cmd[1]
                        possibilities = [folder["name"]for folder in db.get_all_folders() if 
                                            folder["name"].lower() == folder_name.lower()]
                        if folder_name in possibilities: #case sensitive match
                            add_to = folder_name
                            
                        elif len(possibilities) == 0: #no match
                            x = input(f"Folder {folder_name} does not exist yet. Create new folder and add? ")
                            if x.lower() in ("y", "yes"):
                                db.create_folder(folder_name)
                                add_to = folder_name
                            else:
                                print("Action cancelled. ")
                                continue

                        elif len(possibilities) == 1: #insensitive match, 1 option
                            add_to = possibilities[0]

                        else: #insensitive match, > 1 option
                            print("more than one folder with that name: please specify case-sensitively")
                            continue
                        
                        move_flashcard_to_folder_name(id, add_to)
                        print(f"Flashcard moved to {add_to}.")
                        finished = True

                        

    def parse_inbox_cmd(self, s):
        s = s.strip()
        if s in ("1", "2", "3", "4", "5"):
            return ("rate", int(s))
        if s.lower() == "d":
            return ("delete",)
        if s.lower().startswith("e "):
            parts = s[2:].strip().split()
            
            if not parts:
                raise ValueError("No edit provided.")
            
            second_space_index = s.find(" ", s.find(" ") + 1)
            rest = s[second_space_index + 1:] if second_space_index != -1 else ""
            return ("edit", parts[1], rest)
            
        if s.lower().startswith("m "):
            parts = s[2:].strip().split()
            if not parts:
                raise ValueError("No folder name provided.")
            if len(parts) > 1:
                raise ValueError("Only one folder name is allowed.")
            return ("move", parts[0])
        raise ValueError(f"Unrecognized command: '{s}'")


if __name__ == "__main__":
    fire.Fire(CLI(), command=parse_argv(sys.argv[1:]))
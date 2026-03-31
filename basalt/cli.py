import os, logging, shutil, datetime, fire
import sys, json

from basalt.core.config import get_configs, db_path
from basalt.core.core_commands import (set as core_set, capture, review_flashcard, parse_argv, 
                                            clear_cache, clear_configs, clear_db, )
from basalt.core.database import FlashcardDB, ROOT_FOLDER_DEFAULTS

try:
    from basalt.core.daemon import start_daemon
except Exception:  # fallback stub keeps CLI functional when daemon module is absent
    start_daemon = lambda *_, **__: print("start_daemon() not available in this environment")

class CLI:
    """Command-line interface for Basalt.  """

    # ---------- initialisation ----------

    def __init__(self):
        # cache for quick access
        self.configs = get_configs()
        self.db_path = db_path()

    # ---------- high‑level editing ----------

    def set(self, target: str, identifier: str,
            edit_path_or_new_value: str, new_value):
        """Edit a config, folder, or flashcard.

        Examples
        --------
        basalt set config custom_commands.d echo
        basalt set folder Inbox name "My Inbox"
        basalt set card   42    answer "new answer"
        """
        try:
            core_set(target, identifier, edit_path_or_new_value, new_value)
            print("✔ updated.")
        except Exception as e:
            print(f"Error: {e}")

    def capture(self, input=None, file_path_or_url=None, **flags):
        """Send a capture job to the Basalt daemon."""
        try:
            capture(input, file_path_or_url, **flags)
            print("✔ capture job enqueued.")
        except Exception as e:
            print(f"Error: {e}")

    # ---------- maintenance ----------

    def reset(self, *targets, quiet: bool = False):
        """
        Wipe Basalt state.

        • With no targets -> delete db, cache, and configs  
        • Otherwise targets may be any of {'db', 'cache', 'configs'}
        """
        try:
            valid = {"db", "cache", "configs"}

            if targets:
                invalid = [t for t in targets if t not in valid]
                if invalid:
                    raise ValueError(f"Unknown target(s): {', '.join(invalid)}")
                chosen = set(targets)
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
            print("✔ reset complete.")
        except Exception as e:
            print(f"Error: {e}")


    def dev(self, clean: bool = False):
        """Run the daemon in development mode; `--clean` starts from scratch."""
        try:
            if clean:
                clear_db()
                clear_cache()
            start_daemon()
        except Exception as e:
            print(f"Error: {e}")

    # ---------- creators ----------

    def make(self, target: str, *args, **kwargs):
        """
        Create a new card or folder.

        Card
        ----
        basalt make card --question "What is 2+2?" --answer "4" [--key value ...]

        All extra `--key value` pairs become entries in `other_data`.

        Folder
        ------
        basalt make folder <name> [parent]

        • <name>   – new folder’s name  
        • [parent] – parent *id* **or** name (defaults to root “/”)
        """
        try:
            target = target.lower()
            with FlashcardDB(self.db_path) as db:

                # ----- card -----
                if target == "card":
                    if "question" not in kwargs or "answer" not in kwargs:
                        raise ValueError("Card requires --question and --answer")
                    question = kwargs.pop("question")
                    answer = kwargs.pop("answer")
                    card_dict = {"question": question, "answer": answer, **kwargs}
                    batch_id = db.create_batch("")  # trivial batch for singles
                    card_id = db.create_flashcard(card_dict, batch_id)
                    print(f"✔ card {card_id} created.")
                    return

                # ----- folder -----
                if target == "folder":
                    if not args:
                        raise ValueError("Usage: basalt make folder <name> [parent]")
                    folder_name = args[0]
                    parent_arg = args[1] if len(args) > 1 else None
                    new_id = db.create_folder(folder_name)

                    if parent_arg is None:
                        parent_id = ROOT_FOLDER_DEFAULTS["id"]
                    else:
                        if str(parent_arg).isdigit():
                            parent_id = int(parent_arg)
                            db.get_folder(parent_id)
                        else:
                            parent_id = db.get_folder_id_from_name(parent_arg)

                    db.update_folder_fields(new_id, {"parent_id": parent_id})

                    print(f"✔ folder '{folder_name}' (id {new_id}) created.")
                    return

                raise ValueError("Target must be 'card' or 'folder'.")

        except Exception as e:
            print(f"Error: {e}")

    # ---------- listing ----------

    def list(self, what: str = "", target: str = ''):
        """
        Show configs, folder tree, cards, or the raw db.

        `what` ∈ {'config','configs','cards','card','folder','folders',''}
        """
        try:
            what = str(what)
            what = (what or "").strip().lower()

            if what in ("config", "configs"):
                if target:
                    print(json.dumps(self.configs.get(target, {}), indent=2))
                else:
                    print(json.dumps(self.configs, indent=2))
                return

            if what in ("folder", "folders", ""):
                self.display_tree(target)
                return
            
            if what in ("cards", "card"):
                with FlashcardDB(self.db_path) as db:
                    if what == "cards":
                        all_cards = db.get_all_cards()
                        print(json.dumps(all_cards, indent=2))
                        return

                    if not target:
                        raise ValueError("Please supply an ID: basalt list card <id>")
                    if not str(target).isdigit():
                        raise ValueError(f"Card ID must be an integer, got '{target}'")
                    card = db.get_card(int(target))
                    if not card:
                        print(f"Card {target} not found.")
                    else:
                        print(json.dumps(card, indent=2))
                    return
                

            raise ValueError("Argument 'what' not recognised.")
        except Exception as e:
            print(f"Error: {e}")

    # ---------- tree utilities ----------

    def display_tree(self, root=None):
        """Pretty‑print the folder tree starting at *root* (id or name)."""
        try:
            with FlashcardDB(self.db_path) as db:
                root_id = ROOT_FOLDER_DEFAULTS["id"]
                if root:
                    if isinstance(root, int) or (isinstance(root, str) and root.isdigit()):
                        root_id = int(root)
                    else:
                        root_id = db.get_folder_id_from_name(root)
                self.print_folder_tree(db.get_folder_tree(root_id))
                print(db.get_folder_tree(root_id))
        except Exception as e:
            print(f"Error: {e}")

    def print_folder_tree(self, tree, indent=0):
        prefix = "    " * indent + ("├── " if indent else "")
        print(f"{prefix}{tree['name']} (id: {tree['id']})")
        for child in tree["children"]:
            self.print_folder_tree(child, indent + 1)
        for card in tree["cards"]:
            print("    " * (indent + 1) + f"- card {card["id"]}")

    # ---------- inbox ----------

    def inbox(self):
        """Interactive review of all due flashcards."""
        try:
            with FlashcardDB(self.db_path) as db:
                while True:
                    due = db.get_due_cards()
                    if not due:
                        print("🎉  No due cards.")
                        break

                    card = due.pop(0)
                    cid = card["id"]
                    folder = db.get_folder(card["folder_id"])
                    print(f"folder: {folder['name']} | inbox: {len(due)} remaining")
                    print(f"QUESTION: {card['question']}")
                    print(f"ANSWER:   {card['answer']}")
                    if card["other_data"]:
                        print(card["other_data"])

                    while True:
                        try:
                            cmd = self.parse_inbox_cmd(input("> "))

                            if cmd[0] == "quit":
                                print("Exiting inbox.")
                                return
                            if cmd[0] == "rate":
                                review_flashcard(cid, cmd[1])
                                break
                            if cmd[0] == "delete":
                                db.delete_flashcard(cid)
                                break
                            if cmd[0] == "edit":
                                field, value = cmd[1], cmd[2]
                                if field in ("question", "answer"):
                                    db.update_flashcard_fields(cid, {field: value})
                                else:
                                    data = card["other_data"] or {}
                                    data[field] = value
                                    db.update_flashcard_fields(cid, {"other_data": data})
                                break
                            if cmd[0] == "move":
                                self.move_flashcard_to_folder_name(cid, cmd[1])
                                print(f"Flashcard moved to {cmd[1]}.")
                                break

                        except ValueError as err:
                            print(f"Error: {err}")
                            
        except Exception as e:
            print(f"Error: {e}")

    # ---------- helpers ----------

    def move_flashcard_to_folder_name(self, card_id: int, folder_name: str):
        with FlashcardDB(self.db_path) as db:
            folder_id = db.get_folder_id_from_name(folder_name)
            db.update_flashcard_fields(card_id, {"folder_id": folder_id})

    @staticmethod
    def parse_inbox_cmd(s: str):
        s = s.strip().lower()
        if s in {"q", "quit", "exit"}:
            return ("quit",)
        if s in {"1", "2", "3", "4", "5"}:
            return ("rate", int(s))
        if s == "d":
            return ("delete",)
        if s.startswith("e "):
            _, rest = s.split(" ", 1)
            field, _, value = rest.partition(" ")
            if not field or not value:
                raise ValueError("Usage: e <field> <new value>")
            return ("edit", field, value)
        if s.startswith("m "):
            _, folder = s.split(" ", 1)
            folder = folder.strip()
            if not folder:
                raise ValueError("Usage: m <folder>")
            return ("move", folder)
        raise ValueError(f"Unrecognised command: '{s}'")

if __name__ == "__main__":
    fire.Fire(CLI(), command=parse_argv(sys.argv[1:]))

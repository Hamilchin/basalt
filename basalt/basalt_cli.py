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
    """Fire‑based command‑line interface for Basalt.

    All public methods wrap their core logic in try/except so that mistakes
    surface as clean errors instead of tracebacks.
    """

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

    # ---------- listing ----------

    def list(self, what: str = "", target: str = ''):
        """
        Show configs, folder tree, cards, or the raw db.

        `what` ∈ {'config','configs','cards','card','folder','folders',''}
        """
        try:
            what = (what or "").strip().lower()

            if what in ("config", "configs"):
                if target:
                    print(json.dumps(self.configs.get(target, {}), indent=2))
                else:
                    print(json.dumps(self.configs, indent=2))
                return

            if what in ("cards", "card", "folder", "folders", ""):
                self.display_tree(target)
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
                if root is not None:
                    if isinstance(root, int) or (isinstance(root, str) and root.isdigit()):
                        root_id = int(root)
                    else:
                        root_id = db.get_folder_id_from_name(root)
                self.print_folder_tree(db.get_folder_tree(root_id))
        except Exception as e:
            print(f"Error: {e}")

    def print_folder_tree(self, tree, indent=0):
        prefix = "    " * indent + ("├── " if indent else "")
        print(f"{prefix}{tree['name']} (id: {tree['id']})")
        for cid in tree["cards"]:
            print("    " * (indent + 1) + f"- card {cid}")
        for child in tree["children"]:
            self.print_folder_tree(child, indent + 1)

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
                        except ValueError as err:
                            print(f"Error: {err}")
                            continue

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
        except Exception as e:
            print(f"Error: {e}")

    # ---------- helpers ----------

    def move_flashcard_to_folder_name(self, card_id: int, folder_name: str):
        with FlashcardDB(self.db_path) as db:
            folder_id = db.get_folder_id_from_name(folder_name)
            db.update_flashcard_fields(card_id, {"folder_id": folder_id})

    @staticmethod
    def parse_inbox_cmd(s: str):
        s = s.strip()
        if s in {"1", "2", "3", "4", "5"}:
            return ("rate", int(s))
        if s.lower() == "d":
            return ("delete",)
        if s.lower().startswith("e "):
            _, rest = s.split(" ", 1)
            field, _, value = rest.partition(" ")
            if not field or not value:
                raise ValueError("Usage: e <field> <new value>")
            return ("edit", field, value)
        if s.lower().startswith("m "):
            _, folder = s.split(" ", 1)
            folder = folder.strip()
            if not folder:
                raise ValueError("Usage: m <folder>")
            return ("move", folder)
        raise ValueError(f"Unrecognised command: '{s}'")

if __name__ == "__main__":
    fire.Fire(CLI(), command=parse_argv(sys.argv[1:]))

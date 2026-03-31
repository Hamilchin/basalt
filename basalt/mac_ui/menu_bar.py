import rumps
# Needed for callback closures
from typing import Any
import datetime
from basalt.core.spaced_repetition import get_interval_sm2
from basalt.core.datetime_utils import now_dt, dt_to_sql_timestamp
import json
rumps.debug_mode(False)

from basalt.core.database import FlashcardDB
from basalt.core.config import db_path, get_configs

BASE_TITLE = "🪨"
REFRESH_RATE = 1 #seconds
ROOT_FOLDER_DISPLAY = "Folders"


class BasaltApp(rumps.App):
    def __init__(self):
        self.db = FlashcardDB(db_path())
        tree = self._node_to_rumps(self.db.get_folder_tree())

        # Build Capture submenu items from user‑defined hotkeys
        hotkeys = get_configs()["hotkeys"]
        capture_items: list[Any] = []
        for combo, cmd in hotkeys.items():
            capture_items.append(
                rumps.MenuItem(
                    cmd,
                    callback=lambda sender, c=cmd: self.on_capture_command(c)
                )
            )
        if not capture_items:
            capture_items = ["No capture commands"]

        self.tree = {ROOT_FOLDER_DISPLAY : tree[next(iter(tree))]}

        super().__init__(
            "Basalt", 
            title=BASE_TITLE, 
            menu=[
                rumps.MenuItem("Review",  key="r"),
                {"Capture": capture_items},
                self.tree,
                rumps.MenuItem("Settings"),
                None,
            ])

        self.refresh()
        rumps.Timer(self.refresh, REFRESH_RATE).start()

    def _apply_review(self, card: dict[str, Any], score: int) -> None:
        """
        Update spaced‑repetition data for a single flashcard and schedule its
        next due date according to the SM‑2 algorithm.
        """
        # 1. Append the new (score, timestamp) tuple to the card history.
        rep_data = card.get("rep_data") or {"history": []}
        history = rep_data.setdefault("history", [])
        now = now_dt()
        history.append((score, dt_to_sql_timestamp(now)))
        self.db.update_flashcard_fields(card["id"], {"rep_data": rep_data})

        # 2. Compute the next interval/due date.
        folder_settings = self.db.get_folder_settings(card["folder_id"])
        if folder_settings["algorithm"] != "sm2":
            raise NotImplementedError(
                f"Algorithm '{folder_settings['algorithm']}' not yet supported."
            )

        sm2_settings = folder_settings["sm2_settings"]
        interval_hrs = get_interval_sm2(history, sm2_settings)
        next_due = now + datetime.timedelta(hours=interval_hrs)
        self.db.update_flashcard_fields(
            card["id"],
            {"next_due": dt_to_sql_timestamp(next_due)},
        )

    def _review_single(self, card: dict[str, Any]) -> None:
        """
        Present one flashcard in an alert window and record the user's rating.
        """
        other = card.get("other_data") or {}
        other_str = json.dumps(other, indent=2) if other else "—"

        message = (
            f"Q: {card['question']}\n\n"
            f"A: {card['answer']}\n\n"
            f"Other:\n{other_str}"
        )

        # Show alert with four buttons: Again / Hard / Good / Easy
        button_index = rumps.alert(
            title="Basalt Review",
            message=message,
            ok="Again",        # returns 1
            cancel="Hard",     # returns 0
            *["Good", "Easy"]  # return 2 and 3
        )

        # Map button index → SM‑2 grade
        idx_to_grade = {1: 1, 0: 3, 2: 4, 3: 5}
        if button_index == -1:      # user closed the window
            return

        self._apply_review(card, idx_to_grade.get(button_index, 1))

    def _node_to_rumps(self, node: dict[str, Any]) -> dict[str, Any]:
        """
        Recursively build a rumps-compatible menu tree.
        """
        items: list[Any] = []

        for child in node["children"]:
            items.append(self._node_to_rumps(child))
        
        if items:
            items.append(None)

        for card in node["cards"]:
            edit_item   = rumps.MenuItem(
                "Edit",
                callback=lambda sender, cid=card["id"]: self.on_card_edit(cid)
            )
            review_item = rumps.MenuItem(
                "Review",
                callback=lambda sender, cid=card["id"]: self.on_card_review(cid)
            )
            if len(card["question"]) < 10:
                card_menu_display = card["question"]
            else:
                card_menu_display = card["question"][0:10] + "..."

            items.append({card_menu_display: [edit_item, review_item]})

        if not items:
            items = ["No cards"]

        return {node["name"]: items}

    def refresh(self, *_):

        new_tree = self._node_to_rumps(self.db.get_folder_tree())
        contents = new_tree[next(iter(new_tree))]

        folders_menu: rumps.MenuItem = self.menu[ROOT_FOLDER_DISPLAY]
        folders_menu.clear()
        folders_menu.update(contents)

        n = len(self.db.get_due_cards())
        self.title = f"{BASE_TITLE} {n}" if n else BASE_TITLE

    # Card‑level actions

    def on_card_review(self, card_id: int):
        # Placeholder: replace with real review logic
        rumps.alert(f"Review card {card_id}")
        self.refresh()

    def on_card_edit(self, card_id: int):
        # Placeholder: replace with real edit logic
        rumps.alert(f"Edit card {card_id}")

    def on_capture_command(self, command: str):
        # Placeholder: replace with real capture logic
        rumps.alert(f"Capture command executed: {command}")

    def review_loop(self) -> None:
        """
        Walk through every due card and prompt the user for a difficulty
        rating using an alert window that shows the full card content.
        """
        due_cards = self.db.get_due_cards()
        if not due_cards:
            rumps.alert("No cards are due right now!")
            return

        for card in due_cards:
            self._review_single(card)
            # Update menu badge after each review
            self.refresh()

    @rumps.clicked("Review", key="r")
    def on_review(self, sender):
        self.review_loop()


if __name__ == "__main__":
    import threading
    from basalt.hotkey_listener import run_hotkey_listener

    quit_evt   = threading.Event()
    reload_evt = threading.Event()

    threading.Thread(
        target=run_hotkey_listener,
        args=(quit_evt, reload_evt),
        daemon=True
    ).start()

    try:
        app = BasaltApp()
        app.run()

    finally:
        quit_evt.set()
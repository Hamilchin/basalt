import rumps
from datetime import datetime

import os
import sys

def resource_path(filename: str) -> str:
    """
    Return an absolute path to an asset that works both in development
    and when bundled inside a .app (py2app / PyInstaller).
    """
    if getattr(sys, "frozen", False):  # Running from bundled executable
        base = os.path.dirname(sys.executable)
    else:  # Running from source
        base = os.path.dirname(__file__)
    return os.path.join(base, "assets", filename)

class BasaltApp(rumps.App):
    def __init__(self):
        super().__init__("🪨", icon=resource_path("logow.png"), menu=["Review Now", None, "Quit"])
        self.due_cards = [{"id": 1, "question": "What is a monad?"}]
        self.last_review = None
        self.timer = rumps.Timer(self.check_due_cards, 60)  # every 60 sec
        self.timer.start()

    def check_due_cards(self, _):
        if self.due_cards:
            rumps.notification("Basalt", "You have flashcards due.", "Click the menu to review.")
            self.icon = resource_path("logow.png")  # optional dynamic icon

    @rumps.clicked("Review Now")
    def review_card(self, _):
        if not self.due_cards:
            rumps.alert("No cards due!")
            return
        card = self.due_cards.pop(0)
        w = rumps.Window(card["question"], "Answer:", default_text="")
        result = w.run()
        if result.clicked:
            self.log_review(card["id"], result.text)

    def log_review(self, card_id, answer):
        print(f"[{datetime.now()}] Card {card_id} answered: {answer}")
        self.last_review = datetime.now()
        self.icon = None  # reset icon

if __name__ == "__main__":
    BasaltApp().run()
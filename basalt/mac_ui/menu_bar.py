import rumps
rumps.debug_mode(True)

from basalt.core.database import FlashcardDB
from basalt.core.config import db_path

def node_to_rumps(node):
    """Recursively turn a folder-tree node into rumps menu syntax."""
    if not node["children"]:
        return node["name"]
    return {node["name"]:
            [node_to_rumps(c) for c in node["children"]]}

class Demo(rumps.App):
    def __init__(self):

        self.db = FlashcardDB(db_path())

        folders = node_to_rumps(self.db.get_folder_tree(0))
        breakpoint()

        super().__init__(
            "Basalt", 
            title="🪨", 
            menu=[
            rumps.MenuItem("Review",  key="r"),
            {"Capture": [
                rumps.MenuItem("Clipboard", key="1"),      # Cmd-1
                rumps.MenuItem("URL", key="2"),      # Cmd-2
                rumps.MenuItem("", key="3"),      # Cmd-3
            ]}, 
            rumps.MenuItem("Settings", key=","),
            folders, 
            None,
        ])

    @rumps.clicked("Review", key="r")
    def on_review(self, sender):
        pass





if __name__ == "__main__":
    Demo().run()
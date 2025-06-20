
from basalt.core.config import get_configs, get_db_path
from basalt.core.database import FlashcardDB, ROOT_FOLDER_DEFAULTS
from basalt.core.core import move_flashcard_to_folder_name
from basalt.core.spaced_repetition import review_flashcard
import fire, sys, json, os

def list(to_list="", target=None):
    to_list = to_list.strip()
    if to_list not in ("config", "configs", "cards", "folder", "all", "folders", ""):
        raise ValueError("to_list not recognizable")
    elif to_list in ("config", "configs"):
        if not target:
            print(json.dumps(get_configs(), indent=2))
        else:
            print(json.dumps(get_configs()[target], indent=2))
    elif to_list in ("cards", "folder", "folders", ""):
        if not target:
            display_tree()
        else:
            display_tree(target)
    elif to_list in ("all"):
        with FlashcardDB(get_db_path()) as db:
            db.print_db()

def inbox():
    configs = get_configs()
    db_path = os.path.join(configs["data_dir"], "flashcard_data.db")
    with FlashcardDB(db_path) as db:
        while True:
            current_cards = db.get_due_cards()

            if not current_cards:
                print("No due cards. ")
                break
        
            current_card = current_cards.pop(0)
            id, folder_id, batch_id, question, answer, other_data, rep_data, next_due, created_at = current_card["id"], current_card["folder_id"], current_card["batch_id"], current_card["question"], current_card["answer"], current_card["other_data"], current_card["rep_data"], current_card["next_due"], current_card["created_at"]

            current_folder = db.get_folder(folder_id)
            current_batch = db.get_batch(batch_id)

            print(f"folder: {current_folder["folder_name"]} | inbox: {len(current_cards)} remaining")
            print(f"QUESTION: {question}" )
            print(f"ANSWER: {answer}")
            if other_data:
                print(f"{other_data}")

            finished = False

            while not finished:
                cmd = None
                while not cmd:
                    try:
                        cmd = parse_cmd(input())
                    except ValueError as e:
                        print(f"Error: {e}")
                        continue
                
                if cmd[0] == "rate":
                    review_flashcard(id, cmd[1])

                elif cmd[0] == "delete":
                    db.delete_flashcard(id)

                elif cmd[0] == "edit":
                    if cmd[1] in ("question", "answer"):
                        db.update_flashcard_fields(id, {cmd[1]: cmd[2]})
                    else:
                        other_data[cmd[1]] = cmd[2]
                        db.update_flashcard_fields(id, {"other_data" : other_data})

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
                
                print(f"Flashcard moved to {add_to}.")
                move_flashcard_to_folder_name(id, add_to)

def parse_cmd(s):
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

#========== UNIVERSAL UTILITY FUNCTIONS ADD TO CORE ===========

def display_tree(id=ROOT_FOLDER_DEFAULTS["id"]):
    with FlashcardDB(get_db_path()) as database:
        print_folder_tree(database.get_folder_tree(id))

def print_folder_tree(tree, indent=2):
    """Recursively pretty-print a folder tree structure."""
    prefix = "    " * indent + ("├── " if indent else "")
    print(f"{prefix}{tree['name']} (id: {tree['id']})")
    for card_id in tree["cards"]:
        print("    " * (indent + 1) + f"- card {card_id}")
    for child in tree["children"]:
        print_folder_tree(child, indent + 1)


from basalt.core.basalt_commands import set, capture, reset, dev, parse_argv

COMMANDS_DICT = {
    "set": set,
    "capture": capture,
    "reset": reset,
    "dev" : dev, 

    "list": list,
    "inbox" : inbox, 
}

if __name__ == "__main__":
    fire.Fire(COMMANDS_DICT, command=parse_argv())
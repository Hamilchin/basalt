from pynput.keyboard import GlobalHotKeys
from basalt.core.config import get_configs
from basalt.core.basalt_commands import run_command
import shlex

def start_hotkey_listener(): #NEEDS RELOAD FOR CONFIG SETTINGS CHANGE

    configs = get_configs()
    hotkeys = configs["hotkeys"]
    hotkey_handlers = {hk : lambda: run_command(shlex.split(hotkeys[hk])) for hk in hotkeys}

    listener = GlobalHotKeys(hotkey_handlers)

    with listener:
        listener.join()

if __name__ == "__main__":
    start_hotkey_listener()
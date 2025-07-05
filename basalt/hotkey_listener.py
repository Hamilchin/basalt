from basalt.core.config import get_configs
from basalt.core.core_commands import capture, set, parse_argv

from pynput.keyboard import GlobalHotKeys
import threading, fire

CORE_COMMANDS_INTERFACE = {
    "capture" : capture, 
    "set" : set # type: ignore (oops)
}

#small CLI-style interface to make calling things via hotkey_listener easier
def run_command(arg_str: str):
    args = parse_argv(arg_str.split())
    fire.Fire(CORE_COMMANDS_INTERFACE, command=args)

def run_hotkey_listener(quit_event: threading.Event, reload_event:threading.Event):

    while not quit_event.is_set():
        hotkey_map = get_configs()["hotkeys"]

        hotkeys = { keys : lambda 
                   cmd=hotkey_map[keys] : run_command(cmd) 
                   for keys in hotkey_map }

        with GlobalHotKeys(hotkeys) as hk_listener:
            while not reload_event.wait(0.1):
                if quit_event.is_set():
                    return
            reload_event.clear()
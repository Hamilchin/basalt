from ipc_client import send_job
from pynput.keyboard import GlobalHotKeys
from basalt.config import get_configs
from pyperclip import paste

def handle_user_inputs():
    pass

def handle_hotkeys():
    content = paste()
    if content: 
        user_inputs = handle_user_inputs()
        configs = get_configs()
        job = {
            "content": content, 
            "user_inputs": user_inputs, 
            "configs": configs
        }

        send_job(job)

hotkeys = GlobalHotKeys({
    '<cmd>+b': handle_hotkeys
})
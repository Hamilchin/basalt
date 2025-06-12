from pynput.keyboard import GlobalHotKeys
from .core import capture_clipboard, make_flashcard

from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=10)

def handle_keystroke()
    content = capture_clipboard()



def capture():
    executor.submit(handle_keystroke)


    if content:
        try:
            flashcard = make_flashcard(content)
        except Exception as e:
            print(f"An error occurred while creating flashcards: {e}")
    
    return flashcard
    
    

#make-flashcard (prompt, content, )

import requests
from basalt.llm import call_model
from basalt.database import FlashcardDB as db

from pyperclip import paste
import json

def create_prompt(custom_prompt, custom_commands, user_inputs):

    system_prompt = f"""
        You are a flashcard generator for a spaced repetition app. 

        Given this piece of text, extract key ideas that would help the user learn and remember the knowledge
        contained in the text. Assume they've read the text already; your aim should be to jog their mind, and 
        do not over-explain. Represent each as a flashcard object in JSON format with "question" and "answer"
        fields, and possibly more, if the user specifies. Return a single JSON array of such flashcards. 
        
        Use clear, concise phrasing. Each fact should form its own flashcard. 
        Only output valid JSON; no other text. 

    """

    user_prompt = ""

    if custom_prompt.strip() or len(user_inputs) != 0: #is this necessary? 
        user_prompt += "Here are the user's custom instructions: \n"

    for flag, input in user_inputs.items():
        user_prompt += " "
        assert type(input) == str
        if input == "":
            user_prompt += custom_commands[flag]
        else:
            user_prompt += custom_commands[input].replace("{}", input)



    prompt = system_prompt + user_prompt

    return prompt


def extract_json_array(text):

    start, end = text.find('['), text.rfind(']')
    if start == -1 or end == -1:
        raise ValueError("Not wrapped correctly in square brackets")
    
    return json.loads(text[start : end + 1])
    

def make_flashcard(content, user_inputs, configs):

    if content == None:
        raise ValueError("No text content passed to make_flashcard!")

    prompt = create_prompt(configs["custom_prompt"], configs["custom_commands"], user_inputs)

    text_resp = call_model(prompt, content, configs)

    try:
        flashcard = extract_json_array(text_resp)
    except Exception as e:
        print(f"Error when parsing text response as JSON: {e}")
        return None
    
    database = db()

    
import json, os
from basalt.llm import call_model
from basalt.database import FlashcardDB as db

def create_prompt(custom_prompt, custom_commands, user_inputs):

    system_prompt = f"""
        You are a flashcard generator for a spaced repetition app. 

        Given this piece of text, extract a key idea (or ideas) that would help the user learn and remember the knowledge contained in the text. Assume they've read the text already; your aim should be to jog their mind, and do not over-explain. Represent each as a flashcard object in JSON format with "question" and "answer" fields, and possibly more, if the user specifies. Return a single JSON array of such flashcards. 
        
        Use clear, concise phrasing. Each fact should form its own flashcard. 
        Only output valid JSON; no other text. 

    """

    user_prompt = ""

    if custom_prompt.strip() or len(user_inputs) != 0: #is this necessary? 
        user_prompt += "Here are the user's custom instructions: \n"

    for flag, input in user_inputs.items():
        user_prompt += " "
        assert type(input) == str
        if input == True:
            user_prompt += custom_commands[flag]
        else:
            user_prompt += custom_commands[input].replace("{}", str(input))

    prompt = system_prompt + user_prompt

    print(prompt)

    return prompt


def extract_json_array(text):

    start, end = text.find('['), text.rfind(']')
    if start == -1 or end == -1:
        raise ValueError("Not wrapped correctly in square brackets")
    
    return json.loads(text[start : end + 1])


def make_flashcard(content, user_inputs, configs):

    if not content or not configs:
        raise ValueError(f"No {"configs" if not configs else "content"} passed to make_flashcard! (this should never happen)")

    prompt = create_prompt(configs["custom_prompt"], configs["custom_commands"], user_inputs)

    print("model called")

    text_resp = call_model(prompt, content, configs)

    print("model responded")


    try:
        flashcards = extract_json_array(text_resp)
    except Exception as e:
        print(f"Error when parsing text response as JSON: {e}")
        return None
    


    db_path = os.path.join(configs["data_dir"], "flashcard_data.db")

    print("storing content")


    with db(db_path) as database:
        database.store_batch(flashcards, content)

    print("content stored")


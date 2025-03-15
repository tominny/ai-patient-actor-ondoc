import os
from pathlib import Path
import json
import logging

from dotenv import load_dotenv
import jwt
import streamlit as st
from streamlit.web.server.websocket_headers import _get_websocket_headers
from streamlit.components.v1 import html


log = logging.getLogger(__name__)

RESOURCE_DIR = os.getenv("RESOURCE_DIR")
if RESOURCE_DIR:
    RESOURCE_DIR = Path(RESOURCE_DIR)
else:
    RESOURCE_DIR = Path("/data/resources/")

LANGUAGE_CODES = {
    "English": "en-US",
    "German": "de",
    "Spanish": "sp-US",
    "Swahili": "sw-KE",
}


def get_jwt(cookies):
    cookies = cookies.split(";")
    cookie_jar = dict()
    for cookie in cookies:
        split_cookie = cookie.split("=", maxsplit=1)
        cookie_jar.update({split_cookie[0].strip(): split_cookie[1].strip()})
        log.debug("Found cookie: " + cookie)
    log.debug(f"Created cookie jar: {cookie_jar}")
    return cookie_jar.get("JWT")


def validate_jwt(encoded_jwt) -> bool:
    try:
        return jwt.decode(
            encoded_jwt, os.getenv("JWT_PUBLIC_KEY"), algorithms=["RS256"]
        )
    except jwt.ExpiredSignatureError:
        return False


def obtain_key(public_acces=False):
    key = None
    # If public access is granted, just return key
    if public_acces:
        key = os.getenv("OPENAI_API_KEY")
        log.info("Key is public.")
    # If there is a local secrets file, use it
    elif load_dotenv(".streamlit/secrets.toml"):
        key = os.getenv("OPENAI_API_KEY")
        log.info("User uses local API key.")
    # If the requests are coming from a validated user, use the secret API key
    elif is_authenticated():
        key = os.getenv("OPENAI_API_KEY")
        log.info("User uses Dartmouth SSO.")
    return key


def is_authenticated() -> bool:
    headers = _get_websocket_headers()
    log.debug(str(headers))
    cookies = headers.get("Cookie")
    log.debug(cookies)
    token = get_jwt(cookies)
    if token:
        return validate_jwt(token)
    else:
        return False


def get_logging_info(state) -> str:
    s = [f"{key}: {value}" for key, value in state.items() if key != "api_key"]
    return "".join(s)


def reset_app(state, clear_key=False):
    for key in state.keys():
        if key not in [
            "has_footer",
            "case_selection",
            "language_selection",
            "mode_selection",
        ]:
            if clear_key or key != "api_key":
                state.pop(key)
    log.info("App was reset.")


def clear_case_selection(state):
    if "case_selection" in state:
        del state.case_selection


def clear_chat(state):
    state.pop("messages")
    state.pop("conversation")
    state.pop("llm")
    log.info("Message history cleared.")


def on_mode_change(state):
    clear_case_selection(state)
    clear_chat(state)
    log.info("Encounter mode changed.")


patient_personas = {
    "Dany Default": "Just be your regular self.",
    "Fatima the Farmer": """You are a 56-year-old female farmer from Tunbridge, Vermont. Your name is Fatima.
    You rarely use more than 5 words in a sentence. You rarely respond with more than one sentence at a time.""",
    "Billy the Kid": """You are a 5-year old girl named Billy. You talk like a 5-year-old. You are a bit shy and intimidated by
    being in a doctor's office. If the doctor shows some empathy in the conversation, you gradually open up.""",
    "Chatty Chris": """You are a 45-year-old man from Hanover, NH, named Chris. You are very chatty and tend
    to add unnecessary details to your responses.""",
}


def enumerate_cases(mode: str):
    if mode == "Foundational":
        return sorted(
            file.stem for file in (RESOURCE_DIR / "cases" / "neuro").glob("*.txt")
        )
    if mode == "OnDoc":
        return sorted(
            file.stem for file in (RESOURCE_DIR / "cases" / "ondoc").glob("*.txt")
        )


def enumerate_rubrics():
    return sorted(file.stem for file in (RESOURCE_DIR / "rubrics").glob("*txt"))


@st.cache_data
def get_case_description_from_file(file):
    with open(file, "r") as f:
        case = f.read()
    return case


@st.cache_data
def get_case_description(case_id, mode):
    if mode == "Foundational":
        return get_case_description_from_file(
            RESOURCE_DIR / "cases" / "neuro" / f"{case_id}.txt"
        )
    if mode == "OnDoc":
        return get_case_description_from_file(
            RESOURCE_DIR / "cases" / "ondoc" / f"{case_id}.txt"
        )


@st.cache_data
def get_transcript(messages, format="text"):
    if format == "text":
        transcript = ""
        for message in messages:
            transcript += f'{message["role"]}: {message["content"]}\n'
    elif format == "json":
        transcript = json.dumps(
            [
                {"role": message["role"], "message": message["content"]}
                for message in messages
            ]
        )
    else:
        raise NotImplementedError(
            f"[get_transcript]: Unknown format requested: {format}"
        )
    return transcript


@st.cache_data
def get_rubric(rubric_name="default_rubric"):
    with open(RESOURCE_DIR / "rubrics" / f"{rubric_name}.txt", "r") as f:
        rubric = f.read()
    return rubric


def start_encounter(state, reset=False):
    state["encounter_finished"] = False
    if reset:
        reset_app(state)
    log.info("Encounter started.")


def continue_encounter(state):
    state["encounter_finished"] = False
    if "has_footer" in state:
        del state["has_footer"]
    log.info("Encounter continued.")


def end_encounter(state):
    state["encounter_finished"] = True
    if "has_footer" in state:
        del state["has_footer"]
    if "review" in state:
        del state["review"]
    log.info("Encounter ended.")


def move_to_bottom(widget_id, index=0):
    """Moves a streamlit widget below the chat input using its CSS ID

    widget_id: Vale of the widget's 'data-testid' attribute
    index: If there are multiple widgets of the same kind, specify the index of the one to move.
    """

    if index < 0:
        index = f"widgets.length-{-1 * index}"

    html(
        f"""
    <script>
        window.onload = function() {{
            function checkForElements() {{
                let widgetExists = false;
                let chatInputExists = false;
                let chatResponseExists = false;

                // Check if widget_element exists
                widgets = window.parent.document.querySelectorAll("[data-testid='{widget_id}']")
                const widget_element = widgets[{index}];
                if (widget_element) {{
                    widgetExists = true;
                }}

                // Check if chat_input_element exists
                const chat_input_element = window.parent.document.querySelector(".stChatInput");
                if (chat_input_element) {{
                    chatInputExists = true;
                }}

                // Check if chat_response_element exists
                const chat_response_element = window.parent.document.querySelector("[data-testid='stVerticalBlock']");
                if (chat_response_element) {{
                    chatResponseExists = true;
                }}

                // If both elements exist, perform your actions
                if (widgetExists && chatInputExists && chatResponseExists) {{
                    // Check that the widget is not already contained by the chat_input
                    if (chat_input_element.parentElement.lastChild.innerHTML != widget_element.innerHTML){{
                        // Append the child div to the parent div
                        chat_input_element.parentElement.appendChild(widget_element);
                        chat_input_element.parentElement.style.paddingBottom = '20px';
                        // Add margin to top of widget
                        widget_element.style.marginTop = '10px';
                    }}
                }}  else {{
                    // Elements do not exist, wait for a moment and check again
                    setTimeout(checkForElements, 100); // Check again after 1 millisecond
                }}
            }}
            checkForElements();
        }}
    </script>
    """
    )

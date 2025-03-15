import streamlit as st
st.set_page_config(
    page_title="AI Patient Actor",
    page_icon="🤒",
)

from streamlit_mic_recorder import mic_recorder, speech_to_text
from streamlit.components.v1 import html

from openai import OpenAI
from dotenv import load_dotenv

import base64
import datetime
import json
import logging
import os
from pathlib import Path
import time
import uuid

from ai_patient_actor import (
    Assessor,
    LabAssistant,
    PatientActor,
    CasefileConversation,
    StreamHandler,
    AssessmentConversation,
)

import app_utils
from app_utils import (
    clear_chat,
    reset_app,
    enumerate_cases,
    enumerate_rubrics,
    get_case_description,
    get_rubric,
    get_transcript,
    on_mode_change,
    start_encounter,
    continue_encounter,
    end_encounter,
    move_to_bottom,
)

import auth
import db_helper as db

# ---------------- Authentication
if "user" not in st.session_state:
    user = auth.render_auth()
    if not user:
        st.stop()
    st.session_state["user"] = user

# ---------------- App config
MODEL_NAME = "gpt-4o"
MODEL_NAME_ASSESSOR = "gpt-4o"
TTS = OpenAI()

FEEDBACK_SCORES = ["👎", "👍"]

def flag_new_feedback(key):
    if "has_new_feedback" in st.session_state:
        st.session_state["has_new_feedback"].append(key)
    else:
        st.session_state["has_new_feedback"] = [key]

footer = "<div style='opacity:0.6'>Created by <a href=https://geiselmed.dartmouth.edu/thesen>NILE Lab</a> and <a href=https://www.library.dartmouth.edu/research-data-services>RDS @ Dartmouth Library</a>. For questions, please contact <a href='mailto:thomas.thesen@dartmouth.edu?subject=Patient Actor'>Thomas Thesen.</a></div>"

# Preserve sticky widgets.
sticky_widgets = ["case_selection", "language_selection", "mode_selection"]
for k, v in st.session_state.items():
    if k in sticky_widgets:
        st.session_state[k] = v

if "_last_audio_id" not in st.session_state:
    st.session_state._last_audio_id = -1

if "uuid" not in st.session_state:
    st.session_state["uuid"] = uuid.uuid4()

if log_dir := os.getenv("LOG_DIR"):
    log_dir = Path(log_dir)
else:
    log_dir = Path("/data/logs")
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=log_dir / f"{st.session_state['uuid']}.log",
    format="%(asctime)s %(levelname)s: %(message)s",
    encoding="utf-8",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)

log = logging.getLogger(__name__)

@st.cache_data
def log_message(msg):
    log.info(msg)

def fetch_exam_results(exam_type, stream_handler):
    llm = LabAssistant(temperature=0, model_name=MODEL_NAME, streaming=True)
    llm.callbacks = [stream_handler]
    if exam_type == "review":
        exam = "review of systems"
    elif exam_type == "neurological":
        exam = "neurological examination"
    elif exam_type == "physical":
        exam = "physical examination"
    elif exam_type == "diagnostic":
        exam = "diagnostic test"
    else:
        raise NotImplementedError

    return llm.predict(
        f"Describe the results for the {exam} from the following case description. Only take results from one numbered section, but do not repeat the number. Do not add any interpretation or context. Translate to {st.session_state.language}, if necessary. Case description:\n\n"
        + st.session_state["case_description"]
    )

def render_assessment_page(mode="dx"):
    if mode == "dx":
        instructions_section = st.expander("ℹ️ Instructions")
        with instructions_section:
            st.markdown(
                """
                <style>
                code {
                    border-radius: .375rem;
                    border-width: 1px !important;
                    border-color: rgb(213 218 229 / 1) !important;
                    border-style: solid !important;
                    font-family: inherit !important;
                    color: inherit !important;
                    margin: 0.1rem !important;
                }
                </style>
                1. Enter the most likely differential diagnosis.
                2. Hit the `Return` or `Enter` key, or click `Submit` to receive performance feedback.
                For more detailed instructions, [see here](https://geiselmed.dartmouth.edu/thesen/patient-actor-app/).
                """,
                unsafe_allow_html=True,
            )
    st.button(
        label="⬅ Return to Patient Encounter",
        on_click=continue_encounter,
        args=(st.session_state,),
    )
    if mode == "dx":
        with st.form("diagnosis_form"):
            doctors_diagnosis = st.text_input("Please enter the most likely diagnosis")
            submitted = st.form_submit_button("Submit")
    elif mode == "no-dx":
        doctors_diagnosis = None
        submitted = st.button("Get Feedback", use_container_width=True, type="primary")
    else:
        raise NotImplementedError(f"Unknown assessment mode requested: {mode}")

    rubrics = enumerate_rubrics()
    choice = st.selectbox(
        label="Select rubric",
        options=rubrics,
        key="rubric_selection",
    )
    log_message(f"Rubric {choice} requested.")
    rubric = get_rubric(rubric_name=choice)

    if submitted:
        log.info(f"User diagnosis: {doctors_diagnosis}")
        st.markdown("### Review of your performance")
        transcript = get_transcript(st.session_state.messages[1:])
        case_description = st.session_state["case_description"]
        assessor = Assessor(
            openai_api_key=st.session_state["api_key"],
            model_name=MODEL_NAME_ASSESSOR,
            seed=45735737357357,
            temperature=0,
            streaming=True,
        )
        assessment_placeholder = st.empty()
        assessment_stream_handler = StreamHandler(assessment_placeholder)
        assessor.callbacks = [assessment_stream_handler]
        assessment = AssessmentConversation(
            doctors_diagnosis=doctors_diagnosis,
            case_description=case_description,
            interview_transcript=transcript,
            rubric=rubric,
            mode=mode,
            llm=assessor,
            language=st.session_state["language"],
        )
        with st.spinner(""):
            # For no-dx mode, pass an empty input so that the system prompt produces the feedback.
            input_text = "" if mode == "no-dx" else "Evaluate the performance of the medical student. Assess critically and point out what they did correctly and where they can improve. For each rubric section, provide a concrete example of how the student has done well (if appropriate) and how the student could have done better."
            feedback_output = assessment.predict(input=input_text)
            # Only store feedback_output if nonempty
            if feedback_output and feedback_output.strip():
                st.session_state["review"] = feedback_output
            else:
                st.session_state["review"] = "No feedback captured."
        log.info(f"Model assessment: {st.session_state['review']}")
    elif "review" in st.session_state:
        st.markdown("### Review of your performance")
        st.write(st.session_state["review"])

    cols = st.columns(3)
    with cols[0]:
        disabled = True
        if "review" in st.session_state:
            disabled = False
        st.download_button(
            label="Download Transcript",
            data=get_transcript(st.session_state.messages[1:]),
            file_name="transcript.txt",
            mime="text/plain",
            use_container_width=True,
            disabled=disabled,
        )
    with cols[1]:
        dl_review_placeholder = st.empty()
    with cols[2]:
        st.button(
            label="Try Another Case",
            on_click=reset_app,
            args=(st.session_state,),
            use_container_width=True,
        )
    with dl_review_placeholder:
        st.button(label="Download Review", disabled=True, use_container_width=True)
    if "review" in st.session_state:
        with dl_review_placeholder:
            st.download_button(
                label="Download Review",
                data=st.session_state["review"],
                file_name="review.txt",
                mime="text/plain",
                use_container_width=True,
            )

def render_auth_page():
    log.info("User needs to provide own API key.")
    st.warning("No OpenAI API key found!")
    st.button("**Login with Dartmouth SSO**", use_container_width=True)
    url = "/login?redirectUri=/patient-actor"
    html(
        f"""
        <script>
            function redirectToLogin() {{
                window.top.document.getElementById('login-link').click();
            }}
            window.parent.document.querySelector('[kind="secondary"]').addEventListener("click", function(event) {{
                redirectToLogin();
                event.preventDefault();
            }}, false);
            const redirect_link = document.createElement('a');
            redirect_link.href = '{url}';
            redirect_link.target = '_top';
            redirect_link.innerText = 'Invisible Link';
            redirect_link.style = 'display:none;';
            redirect_link.id = 'login-link';
            window.top.document.body.appendChild(redirect_link);
        </script>
        <style="padding:0px"></style>
        """,
        height=0,
    )
    st.markdown("<p style='text-align: center;'><b>or</b></p>", unsafe_allow_html=True)
    html("", height=0)
    with st.form("key_prompt"):
        key = st.text_input("Please provide an active OpenAI API key")
        consent_given = st.checkbox("I know that the owner of this API key will be charged for the use of GPT-4 in this session. See [here](https://openai.com/pricing) for more info.")
        submitted = st.form_submit_button("Submit")
        if not submitted:
            st.stop()
        if not consent_given:
            st.warning("Please confirm that you are aware of the API cost to proceed.")
            st.stop()
    return key

def render_exam_result(exam_type, rerun):
    with st.chat_message("exam", avatar="🩺"):
        message_placeholder = st.empty()
        with st.spinner(""):
            st.session_state.messages.append(
                {
                    "role": "exam",
                    "avatar": "🩺",
                    "content": fetch_exam_results(
                        exam_type=exam_type,
                        stream_handler=StreamHandler(message_placeholder),
                    ),
                }
            )
        log.info(f"Results of '{exam_type}': {st.session_state.messages[-1]['content']}")
    if rerun:
        st.rerun()

def render_settings():
    col1, col2, col3 = st.columns(3)
    with col1:
        st.session_state["encounter_mode"] = st.radio(
            label="Mode selection",
            options=["Foundational", "OnDoc"],
            horizontal=True,
            on_change=on_mode_change,
            args=(st.session_state,),
            key="mode_selection",
        )
    log_message(f"Mode {st.session_state['encounter_mode']} requested.")
    cases = enumerate_cases(mode=st.session_state.encounter_mode)
    col11, col12 = st.columns(2)
    with col11:
        st.session_state["input_mode"] = st.radio(
            label="Doctor input",
            options=["Text-only", "Speech + Text"],
            horizontal=True,
        )
    with col12:
        st.session_state["output_mode"] = st.radio(
            label="Patient response",
            options=["Text", "Speech"],
            horizontal=True,
        )
    with col2:
        choice = st.selectbox(
            label="Select case",
            options=cases,
            on_change=clear_chat,
            args=(st.session_state,),
            key="case_selection",
        )
    log_message(f"Case {choice} requested.")
    st.session_state["case_description"] = get_case_description(
        choice, mode=st.session_state.encounter_mode
    )
    language_options = ["English", "German", "Spanish", "Swahili"]
    with col3:
        language = st.selectbox(
            label="Select language",
            options=language_options,
            on_change=clear_chat,
            args=(st.session_state,),
            key="language_selection",
        )
    log_message(f"Language {language} requested.")
    st.session_state["language"] = language

def replace_chat_input_text(text, pos):
    js = f"""
        <script>
            function insertText(dummy_var_to_force_repeat_execution) {{
                var chatInput = parent.document.querySelector('textarea[data-testid="stChatInputTextArea"]');
                if (chatInput){{
                    var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set;
                    nativeInputValueSetter.call(chatInput, "{text}");
                    var event = new Event('input', {{ bubbles: true}});
                    chatInput.dispatchEvent(event);
                }} else {{
                    setTimeout(insertText, 100);
                }}
            }}
            insertText({pos});
        </script>
    """
    html(js)

def submit_feedback(feedback, subject):
    if log.root.hasHandlers():
        logfile_path = log.root.handlers[0].baseFilename
    with open(logfile_path) as log_file:
        log_history = log_file.read()
    feedback["log"] = log_history
    feedback["subject"] = subject
    if FEEDBACK_DIR := os.getenv("FEEDBACK_DIR"):
        filepath = Path(FEEDBACK_DIR)
    else:
        filepath = Path("/data/feedback")
    filepath.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().timestamp()
    with open(
        filepath / f"feedback-{st.session_state['uuid']}-{timestamp}.json", "w"
    ) as f:
        json.dump(feedback, f)

def text_to_speech(text, play_immediately=True, blocking=False):
    tts_response = TTS.audio.speech.create(
        model="tts-1",
        voice="alloy",
        input=text,
    )
    sampling_rate = 16_000
    data = bytes()
    for chunk in tts_response.iter_bytes():
        data += chunk
    audio_length = len(data) / sampling_rate
    audio_base64 = base64.b64encode(data).decode("utf-8")
    if play_immediately:
        audio_tag = f'<audio autoplay="true" src="data:audio/wav;base64,{audio_base64}">'
        st.markdown(audio_tag, unsafe_allow_html=True)
        if blocking:
            time.sleep(audio_length)
    return audio_base64

col1, col2, col3 = st.columns(3)
with col1:
    st.image("./resources/images/dartmouth-libraries-logo.png")
with col3:
    st.image("./resources/images/neuro-course-logo.png")

st.markdown(
    """<style>
[data-testid="column"] {
    width: calc(33.3333% - 1rem) !important;
    flex: 1 1 calc(33.3333% - 1rem) !important;
    min-width: calc(33% - 1rem) !important;
}
</style>""", 
    unsafe_allow_html=True,
)

st.markdown(
    "<h1 style='text-align: center;'>🤒 AI Patient Actor Playground 🧑‍⚕️</h1>",
    unsafe_allow_html=True,
)

if "api_key" not in st.session_state:
    log.info("Session started.")
    key = app_utils.obtain_key(public_acces=True)
    if not key:
        key = render_auth_page()
    st.session_state["api_key"] = key
    st.rerun()

if "encounter_finished" not in st.session_state:
    start_encounter(st.session_state)

if not st.session_state.encounter_finished:
    instructions_section = st.expander("ℹ️ Instructions")
    with st.expander("⚙️ Settings", expanded=True):
        render_settings()
    end_button_label = "End Patient Encounter and Receive Feedback"
    with instructions_section:
        if not st.session_state.get("encounter_finished"):
            st.markdown(
                f"""
                <style>
                code {{
                    border-radius: .375rem;
                    border-width: 1px !important;
                    border-color: rgb(213 218 229 / 1) !important;
                    border-style: solid !important;
                    font-family: inherit !important;
                    color: inherit !important;
                    margin: 0.1rem !important;
                }}
                </style>
                1. Select a case from the dropdown menu.
                2. Enter prompts in the field to interact with the AI Patient Actor as you would in a clinical encounter.
                3. To order a test or perform an exam, click the corresponding button.
                4. Click `{end_button_label}` when ready to receive feedback.
                For more detailed instructions, [see here](https://geiselmed.dartmouth.edu/thesen/patient-actor-app/).
                """,
                unsafe_allow_html=True,
            )
    st.button(
        label="**" + end_button_label + "**",
        on_click=end_encounter,
        args=(st.session_state,),
        use_container_width=True,
        type="primary",
    )
    if "llm" not in st.session_state:
        st.session_state.llm = PatientActor(
            openai_api_key=st.session_state["api_key"],
            model_name=MODEL_NAME,
            streaming=st.session_state.output_mode == "Text",
            temperature=0,
        )
    llm = st.session_state.llm
    llm.streaming = st.session_state.output_mode == "Text"
    if "conversation" not in st.session_state:
        st.session_state.conversation = CasefileConversation(
            case_description=st.session_state["case_description"],
            llm=llm,
            language=st.session_state.language,
        )
    conversation = st.session_state.conversation
    st.markdown("## AI Patient interview")
    if "messages" not in st.session_state:
        intro_text = """
        **Welcome to the AI Patient Actor!**
        """
        intro_message = {"role": "intro", "avatar": "💬", "content": intro_text}
        st.session_state.messages = [intro_message]
    n = 0
    for message in st.session_state.messages:
        with st.chat_message(message["role"], avatar=message["avatar"]):
            st.markdown(message["content"])
        if message["role"] in ["patient", "exam"]:
            feedback_key = f"feedback_{n}"
            n += 1
            if feedback_key not in st.session_state:
                st.session_state[feedback_key] = None
            feedback = st.feedback(
                options="thumbs",
                key=feedback_key,
                on_change=flag_new_feedback,
                args=(feedback_key,),
            )
            if (
                feedback is not None
                and st.session_state.get("has_new_feedback")
                and feedback_key in st.session_state["has_new_feedback"]
            ):
                submit_feedback(
                    {"type": "thumbs", "score": FEEDBACK_SCORES[feedback]}, message
                )
                st.session_state["has_new_feedback"].remove(feedback_key)
    if prompt := st.chat_input("Interview the patient and establish a diagnosis"):
        st.session_state.messages.append(
            {"role": "doctor", "avatar": "🧑‍⚕️", "content": prompt}
        )
        with st.chat_message("doctor", avatar="🧑‍⚕️"):
            st.markdown(prompt)
        log.info(f"User message: {prompt}")
        with st.chat_message("patient", avatar="🤒"):
            message_placeholder = st.empty()
            if llm.streaming:
                stream_handler = StreamHandler(message_placeholder)
                llm.callbacks = [stream_handler]
            try:
                with st.spinner(""):
                    response = conversation.run(
                        input=st.session_state.messages[-1]["content"]
                    )
                    log.info(f"Model response: {response}")
            except Exception as e:
                message = str(e)
                log.info("Provided API key invalid.")
                st.error(message)
                st.button(
                    "⬅ Go Back to Enter Valid Key",
                    on_click=reset_app,
                    args=(st.session_state, True),
                )
                st.stop()
            if st.session_state.output_mode == "Speech":
                with st.spinner(""):
                    text_to_speech(response, play_immediately=True, blocking=True)
            st.session_state.messages.append(
                {"role": "patient", "avatar": "🤒", "content": response}
            )
            st.rerun()
    if len(st.session_state.messages) <= 1:
        replace_chat_input_text(
            text="Hi! I am Dr. X. What brings you to the clinic today?",
            pos=len(st.session_state.messages),
        )
    if "has_footer" not in st.session_state:
        st.markdown(footer, unsafe_allow_html=True)
        move_to_bottom("stMarkdownContainer", index=-4)
        st.session_state["has_footer"] = True
    if st.session_state.input_mode == "Speech + Text":
        transcription = speech_to_text(
            start_prompt="🎤 Start recording",
            stop_prompt="⏹️ Stop recording",
            just_once=True,
            language=app_utils.LANGUAGE_CODES[st.session_state.language],
        )
        if transcription:
            replace_chat_input_text(
                text=transcription, pos=len(st.session_state.messages)
            )
    cols = st.columns(3)
    with cols[0]:
        do_physical = st.button("Physical Examination", use_container_width=True)
    if do_physical:
        render_exam_result("physical", rerun=True)
    with cols[1]:
        do_neuro = st.button("Neurological Examination", use_container_width=True)
    if do_neuro:
        render_exam_result("neurological", rerun=True)
    with cols[2]:
        do_dx = st.button("Diagnostic Tests", use_container_width=True)
    if do_dx:
        render_exam_result("diagnostic", rerun=True)
else:  # Patient encounter is finished
    if st.session_state["encounter_mode"] == "Foundational":
        render_assessment_page(mode="dx")
    elif st.session_state["encounter_mode"] == "OnDoc":
        render_assessment_page(mode="no-dx")
    st.markdown(footer, unsafe_allow_html=True)
    hide_streamlit_style = """
        <style>
        footer {visibility: hidden;}
        </style>
    """
    st.markdown(hide_streamlit_style, unsafe_allow_html=True)
    # --- Save the interaction (transcript and feedback) once per session.
    if "interaction_saved" not in st.session_state:
        transcript = get_transcript(st.session_state.messages[1:])
        feedback_text = st.session_state.get("review")
        if not feedback_text or feedback_text.strip() == "":
            feedback_text = "No feedback captured."
        user_id = st.session_state["user"]["id"]
        saved = db.save_interaction(user_id, transcript, feedback_text)
        if saved:
            st.session_state["interaction_saved"] = True
            st.info("Interaction saved successfully!")
        else:
            st.error("Error saving interaction.")

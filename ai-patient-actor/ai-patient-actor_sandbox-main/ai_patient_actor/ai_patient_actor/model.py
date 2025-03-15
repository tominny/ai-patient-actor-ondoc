from typing import Any
from langchain.chat_models import ChatOpenAI
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
from langchain.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder,
    HumanMessagePromptTemplate,
)
from ai_patient_actor import (
    sandbox_system_message,
    case_file_system_message,
    assessment_system_message,
    assessment_no_dx_system_message,
)


class Assessor(ChatOpenAI):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class LabAssistant(ChatOpenAI):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class PatientActor(ChatOpenAI):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class SandboxConversation(ConversationChain):
    def __init__(self, case_description, persona, **kwargs):
        memory = ConversationBufferMemory(
            memory_key="history",
            return_messages=True,
            ai_prefix="Patient",
            human_prefix="Doctor",
        )
        kwargs["memory"] = memory

        system_message_prompt = sandbox_system_message.format(
            case_description=case_description,
            patient_persona=persona,
        )
        chat_prompt = ChatPromptTemplate.from_messages(
            [
                system_message_prompt,
                MessagesPlaceholder(variable_name="history"),
                HumanMessagePromptTemplate.from_template("{input}"),
            ]
        )

        kwargs["prompt"] = chat_prompt
        super().__init__(**kwargs)


class CasefileConversation(ConversationChain):
    def __init__(self, case_description, language="US English", **kwargs):
        memory = ConversationBufferMemory(
            memory_key="history",
            return_messages=True,
            ai_prefix="Patient",
            human_prefix="Doctor",
        )
        kwargs["memory"] = memory

        system_message_prompt = case_file_system_message.format(
            case_description=case_description, language=language
        )
        chat_prompt = ChatPromptTemplate.from_messages(
            [
                system_message_prompt,
                MessagesPlaceholder(variable_name="history"),
                HumanMessagePromptTemplate.from_template("{input}"),
            ]
        )

        kwargs["prompt"] = chat_prompt
        super().__init__(**kwargs)


class AssessmentConversation(ConversationChain):
    def __init__(
        self,
        doctors_diagnosis,
        case_description,
        interview_transcript,
        rubric,
        mode="dx",
        language="US English",
        **kwargs: Any,
    ) -> None:
        memory = ConversationBufferMemory(
            memory_key="history",
            return_messages=True,
            ai_prefix="Assessor",
            human_prefix="Doctor",
        )
        kwargs["memory"] = memory
        if mode == "dx":
            system_message_prompt = assessment_system_message.format(
                diagnosis=doctors_diagnosis,
                rubric=rubric,
                case_description=case_description,
                transcript=interview_transcript,
                language=language,
            )
        elif mode == "no-dx":
            system_message_prompt = assessment_no_dx_system_message.format(
                rubric=rubric,
                case_description=case_description,
                transcript=interview_transcript,
                language=language,
            )
        else:
            raise NotImplementedError(f"Unknown assessment mode specified: {mode}")

        chat_prompt = ChatPromptTemplate.from_messages(
            [
                system_message_prompt,
                MessagesPlaceholder(variable_name="history"),
                HumanMessagePromptTemplate.from_template("{input}"),
            ]
        )
        kwargs["prompt"] = chat_prompt
        super().__init__(**kwargs)

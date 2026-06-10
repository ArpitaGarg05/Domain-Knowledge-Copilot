from dataclasses import dataclass
from typing import Optional

from groq import Groq, GroqError

from app.core.config import settings
from app.models.chat_message import ChatMessage
from app.services.vector_store_service import RetrievalResult


class LLMConfigurationError(RuntimeError):
    pass


class LLMGenerationError(RuntimeError):
    pass


@dataclass(frozen=True)
class GeneratedAnswer:
    answer: str


class LLMService:
    def __init__(
        self,
        api_key: Optional[str] = settings.groq_api_key,
        model: str = settings.groq_model,
    ) -> None:
        self.api_key = api_key
        self.model = model

    def generate_answer(
        self,
        question: str,
        chunks: list[RetrievalResult],
        history: Optional[list[ChatMessage]] = None,
    ) -> GeneratedAnswer:
        if not self.api_key:
            raise LLMConfigurationError("GROQ_API_KEY is not configured.")

        prompt = self.build_prompt(question=question, chunks=chunks, history=history or [])
        client = Groq(api_key=self.api_key)

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a domain knowledge assistant. Answer only from "
                            "the provided retrieved sources. If the sources do not "
                            "contain the answer, say you do not have enough "
                            "information in the corpus."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
            )
        except GroqError as error:
            raise LLMGenerationError(str(error)) from error

        answer = response.choices[0].message.content or ""
        return GeneratedAnswer(answer=answer.strip())

    def build_prompt(
        self,
        question: str,
        chunks: list[RetrievalResult],
        history: list[ChatMessage],
    ) -> str:
        conversation_history = "\n".join(
            f"{message.role}: {message.content}"
            for message in history
        )
        sources = "\n\n".join(
            (
                f"Source {index} "
                f"(file={chunk.filename}, page={chunk.page_number}, "
                f"chunk_ref={chunk.chunk_reference}):\n{chunk.text}"
            )
            for index, chunk in enumerate(chunks, start=1)
        )

        return (
            "Recent conversation:\n"
            f"{conversation_history if conversation_history else 'No prior messages.'}\n\n"
            "Question:\n"
            f"{question}\n\n"
            "Retrieved sources:\n"
            f"{sources if sources else 'No retrieved sources.'}\n\n"
            "Answer:"
        )

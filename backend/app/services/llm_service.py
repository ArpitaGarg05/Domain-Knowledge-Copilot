from dataclasses import dataclass

from groq import Groq, GroqError

from app.core.config import settings
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
        api_key: str | None = settings.groq_api_key,
        model: str = settings.groq_model,
    ) -> None:
        self.api_key = api_key
        self.model = model

    def generate_answer(
        self,
        question: str,
        chunks: list[RetrievalResult],
    ) -> GeneratedAnswer:
        if not self.api_key:
            raise LLMConfigurationError("GROQ_API_KEY is not configured.")

        prompt = self.build_prompt(question=question, chunks=chunks)
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

    def build_prompt(self, question: str, chunks: list[RetrievalResult]) -> str:
        sources = "\n\n".join(
            (
                f"Source {index} "
                f"(document_id={chunk.document_id}, page={chunk.page_number}, "
                f"chunk_id={chunk.chunk_id}):\n{chunk.text}"
            )
            for index, chunk in enumerate(chunks, start=1)
        )

        return (
            "Question:\n"
            f"{question}\n\n"
            "Retrieved sources:\n"
            f"{sources if sources else 'No retrieved sources.'}\n\n"
            "Answer:"
        )

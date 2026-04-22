import os
from openai import OpenAI
from brain.providers.base import Provider


class OpenAIProvider(Provider):
    def __init__(self, model: str = "gpt-4o", max_tokens: int = 1024, base_url: str | None = None):
        self.client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY", "none"),
            base_url=base_url,
        )
        self.model = model
        self.max_tokens = max_tokens

    def complete(self, system: str, user: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content

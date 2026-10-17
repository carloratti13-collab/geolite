"""Local Qwen 2.5 Coder 0.5B adapter used for grounded answers."""
from __future__ import annotations


class QwenLocal:
    """Lazy loader: model weights are downloaded only when requested."""

    def __init__(self, model_id: str = "Qwen/Qwen2.5-Coder-0.5B-Instruct") -> None:
        self.model_id = model_id
        self._pipeline = None

    def generate(self, prompt: str, max_new_tokens: int = 180) -> str:
        if self._pipeline is None:
            from transformers import pipeline

            self._pipeline = pipeline("text-generation", model=self.model_id, device_map="auto", torch_dtype="auto")
        result = self._pipeline(
            prompt,
            max_new_tokens=min(max_new_tokens, 180),
            do_sample=False,
            return_full_text=False,
        )
        return result[0]["generated_text"]
from __future__ import annotations

from abc import ABC, abstractmethod

from PIL import Image


class OCRProvider(ABC):
    name: str
    model_name: str

    @abstractmethod
    def extract_text(self, image: Image.Image, prompt: str) -> str:
        raise NotImplementedError

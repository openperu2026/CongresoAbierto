from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

import torch
from PIL import Image

from backend.ocr.providers.base import OCRProvider


class DeepSeekOCRProvider(OCRProvider):
    def __init__(
        self,
        model_name: str = "deepseek-ai/DeepSeek-OCR",
        *,
        device: str = "cuda",
        torch_dtype: torch.dtype = torch.bfloat16,
        trust_remote_code: bool = True,
    ):
        from transformers import AutoModel, AutoTokenizer

        self.name = "deepseek"
        self.model_name = model_name

        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            trust_remote_code=trust_remote_code,
        )
        self.model = AutoModel.from_pretrained(
            model_name,
            _attn_implementation="eager",
            trust_remote_code=trust_remote_code,
            use_safetensors=True,
            torch_dtype=torch_dtype,
        )

        self.model = self.model.to(device).eval()

        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token_id = self.tokenizer.eos_token_id

        if getattr(self.model, "generation_config", None) is not None:
            self.model.generation_config.pad_token_id = self.tokenizer.pad_token_id
            if self.model.generation_config.eos_token_id is None:
                self.model.generation_config.eos_token_id = self.tokenizer.eos_token_id

    def extract_text(self, image: Image.Image, prompt: str) -> str:
        tmp = NamedTemporaryFile(suffix=".png", delete=False)
        tmp_path = Path(tmp.name)
        tmp.close()
        image.save(tmp_path, format="PNG")

        try:
            text = self.model.infer(
                self.tokenizer,
                prompt=prompt,
                image_file=str(tmp_path),
                output_path=str(tmp_path.parent),
                base_size=1024,
                image_size=640,
                crop_mode=True,
                test_compress=False,
                save_results=False,
                eval_mode=True,
            )
        finally:
            tmp_path.unlink(missing_ok=True)

        return text

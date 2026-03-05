# backend/app/services/summarizer_service.py

import logging
import warnings

warnings.filterwarnings("ignore")
import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

logger = logging.getLogger(__name__)


class SummarizerService:
    """
    Summarization service using FLAN-T5 model.
    Lazy-loads the model on first use to avoid startup delays.
    """

    def __init__(self, model_name: str = "google/flan-t5-large"):
        self.model_name = model_name
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = None
        self.tokenizer = None
        self._init_attempted = False

    def _ensure_loaded(self) -> bool:
        if self.model is not None and self.tokenizer is not None:
            return True
        if self._init_attempted:
            return False

        self._init_attempted = True
        try:
            logger.info(
                "Loading summarization model '%s' on %s...",
                self.model_name,
                self.device.upper(),
            )
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name)
            self.model.to(self.device)
            self.model.eval()
            logger.info("Summarization model loaded successfully.")
            return True
        except Exception:
            logger.exception("Failed to load summarization model")
            self.model = None
            self.tokenizer = None
            return False

    def summarize(self, text: str) -> str:
        """
        Summarize the given text using the FLAN-T5 model.
        """
        if not self._ensure_loaded():
            return "Summarizer model not available."

        if not text or len(text.strip()) < 50:
            return "Text too short to summarize."

        try:
            max_input_length = 2000
            if len(text) > max_input_length:
                text = text[:max_input_length] + "..."

            prompt = (
                "Summarize the following transcript in a clear, concise way:\n\n"
                f"{text}\n\nSummary:"
            )

            inputs = self.tokenizer(
                prompt,
                return_tensors="pt",
                max_length=2048,
                truncation=True
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=200,
                    do_sample=False,
                    temperature=0.7,
                    num_beams=2,
                    early_stopping=True
                )

            generated_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            return generated_text.strip()
        except Exception as e:
            logger.exception("Summarization failed")
            return f"Summarization failed: {str(e)}"


summarizer_service = SummarizerService()


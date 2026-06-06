"""AutoVLA LoRA generation-SFT helpers (step 2).

Turns the instruction examples from ``autovla_format`` into chat-formatted,
label-masked tensors for next-token training of a Qwen2.5-VL model: the prompt
(system/user + image placeholders) is masked with -100 so the loss only covers
the assistant completion (reasoning + action tokens).

The multimodal collator needs image pixels (processor); the tokenizer/masking
helpers here are image-free and unit-testable.
"""
from __future__ import annotations

from typing import Any

IGNORE_INDEX = -100


def register_action_tokens(tokenizer: Any, num_tokens: int) -> int:
    """Add ``<act_i>`` special tokens so each maps to a single id.

    Returns the number of newly added tokens. Caller must
    ``model.resize_token_embeddings(len(tokenizer))`` after this.
    """
    from vla_drive.data.autovla_format import action_special_tokens

    specials = action_special_tokens(num_tokens)
    return int(tokenizer.add_special_tokens({"additional_special_tokens": specials}))


def build_chat_messages(prompt: str, completion: str, num_images: int) -> tuple[list[dict], list[dict]]:
    """Return (full_messages, prompt_only_messages) for a chat template.

    full = user(images+prompt) + assistant(completion).
    prompt_only = user(images+prompt)  → used with add_generation_prompt=True to
    measure the prefix length to mask.
    """
    user_content = [{"type": "image"} for _ in range(max(0, int(num_images)))]
    user_content.append({"type": "text", "text": prompt})
    user_msg = {"role": "user", "content": user_content}
    assistant_msg = {"role": "assistant", "content": [{"type": "text", "text": completion}]}
    return [user_msg, assistant_msg], [user_msg]


def mask_prompt_prefix(input_ids: list[int], prompt_len: int) -> list[int]:
    """labels = input_ids with the first prompt_len positions set to IGNORE_INDEX."""
    prompt_len = max(0, min(int(prompt_len), len(input_ids)))
    return [IGNORE_INDEX] * prompt_len + list(input_ids[prompt_len:])


class AutoVLASFTCollator:
    """Collate AutoVLA instruction examples into Qwen2.5-VL SFT batches.

    Each example is a dict from ``autovla_format.build_instruction_example``
    (prompt, completion, image_paths). Runtime use needs image pixels.
    """

    def __init__(self, processor: Any, image_size: int | None = None,
                 image_retries: int = 3, retry_wait_s: float = 2.0) -> None:
        self.processor = processor
        self.image_size = image_size
        self.image_retries = image_retries
        self.retry_wait_s = retry_wait_s

    def _load_images(self, paths):
        """Load images with retries (rides out brief volume unmounts). None if unreadable."""
        import time

        from PIL import Image

        for attempt in range(max(1, self.image_retries)):
            try:
                imgs = [Image.open(p).convert("RGB") for p in paths]
                if self.image_size:
                    imgs = [im.resize((self.image_size, self.image_size)) for im in imgs]
                return imgs
            except (FileNotFoundError, OSError):
                if attempt < self.image_retries - 1:
                    time.sleep(self.retry_wait_s)
        return None

    def __call__(self, examples: list[dict]) -> dict:
        full_texts: list[str] = []
        prompt_texts: list[str] = []
        images_per_sample: list[list[Any]] = []
        kept: list[dict] = []
        for ex in examples:
            imgs = self._load_images(ex["image_paths"])
            if imgs is None:  # unreadable (e.g., volume briefly unmounted) → drop sample
                continue
            full_msgs, prompt_msgs = build_chat_messages(
                ex["prompt"], ex["completion"], num_images=len(ex["image_paths"])
            )
            full_texts.append(
                self.processor.apply_chat_template(full_msgs, tokenize=False, add_generation_prompt=False)
            )
            prompt_texts.append(
                self.processor.apply_chat_template(prompt_msgs, tokenize=False, add_generation_prompt=True)
            )
            images_per_sample.append(imgs)
            kept.append(ex)

        if not kept:  # whole batch unreadable → signal trainer to skip this step
            return None
        examples = kept
        flat_images = [im for imgs in images_per_sample for im in imgs]
        batch = self.processor(
            text=full_texts, images=flat_images, return_tensors="pt", padding=True
        )
        # Per-sample prompt length (with the same images) → mask the prefix.
        labels = batch["input_ids"].clone()
        labels[:] = IGNORE_INDEX
        for i, ex in enumerate(examples):
            prompt_ids = self.processor(
                text=[prompt_texts[i]], images=images_per_sample[i], return_tensors="pt", padding=False
            )["input_ids"][0]
            prompt_len = int(prompt_ids.shape[0])
            full_ids = batch["input_ids"][i]
            labels[i, prompt_len:] = full_ids[prompt_len:]
        # Do not learn padding.
        pad_id = self.processor.tokenizer.pad_token_id
        if pad_id is not None:
            labels[batch["input_ids"] == pad_id] = IGNORE_INDEX
        batch["labels"] = labels
        return batch

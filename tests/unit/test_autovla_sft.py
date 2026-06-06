from __future__ import annotations

from vla_drive.data.autovla_sft import (
    IGNORE_INDEX,
    build_chat_messages,
    mask_prompt_prefix,
    register_action_tokens,
)


def test_mask_prompt_prefix() -> None:
    ids = [10, 11, 12, 13, 14]
    labels = mask_prompt_prefix(ids, 3)
    assert labels == [IGNORE_INDEX, IGNORE_INDEX, IGNORE_INDEX, 13, 14]
    # clamp out-of-range
    assert mask_prompt_prefix(ids, 99) == [IGNORE_INDEX] * 5
    assert mask_prompt_prefix(ids, 0) == ids


def test_build_chat_messages_shapes() -> None:
    full, prompt_only = build_chat_messages("do it", "answer <act_1>", num_images=3)
    assert len(full) == 2 and full[0]["role"] == "user" and full[1]["role"] == "assistant"
    # 3 image placeholders + 1 text in the user turn.
    image_items = [c for c in full[0]["content"] if c["type"] == "image"]
    text_items = [c for c in full[0]["content"] if c["type"] == "text"]
    assert len(image_items) == 3 and len(text_items) == 1
    assert full[1]["content"][0]["text"] == "answer <act_1>"
    # prompt-only drops the assistant turn.
    assert len(prompt_only) == 1 and prompt_only[0]["role"] == "user"


class _FakeTokenizer:
    def __init__(self) -> None:
        self.added: list[str] = []

    def add_special_tokens(self, mapping: dict) -> int:
        toks = mapping["additional_special_tokens"]
        self.added.extend(toks)
        return len(toks)


def test_register_action_tokens() -> None:
    tok = _FakeTokenizer()
    n = register_action_tokens(tok, 16)
    assert n == 16
    assert tok.added[0] == "<act_0>" and tok.added[-1] == "<act_15>"

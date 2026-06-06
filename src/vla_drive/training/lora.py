from __future__ import annotations

import torch.nn as nn


def apply_lora(
    model: nn.Module,
    rank: int = 8,
    alpha: int = 16,
    modules_to_save: list[str] | None = None,
) -> nn.Module:
    """Attach PEFT LoRA adapters to the LLM attention layers and return the wrapped model.

    modules_to_save: extra modules trained fully (not low-rank). For AutoVLA
    generation pass ["embed_tokens", "lm_head"] so the newly added ``<act_i>``
    token rows are actually learned.
    """
    from peft import LoraConfig, TaskType, get_peft_model

    # q_proj/k_proj/v_proj/o_proj target the LLM self-attention layers.
    # Qwen2.5-VL vision encoder uses fused qkv/proj names, so these patterns
    # do not accidentally target the vision tower.
    config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=rank,
        lora_alpha=alpha,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        lora_dropout=0.05,
        bias="none",
        modules_to_save=modules_to_save,
    )
    return get_peft_model(model, config)

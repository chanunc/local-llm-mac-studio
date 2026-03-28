# Copyright (c) 2026
#
# Local patch module for Mistral 4 text support in mlx_lm.

import math
from dataclasses import dataclass
from typing import Any, Dict, Optional

import mlx.core as mx
import mlx.nn as nn

from .activations import swiglu
from .base import BaseModelArgs, create_attention_mask, scaled_dot_product_attention
from .pipeline import PipelineMixin
from .rope_utils import initialize_rope
from .switch_layers import SwitchGLU


@dataclass
class ModelArgs(BaseModelArgs):
    model_type: str = "mistral4"
    vocab_size: int = 131072
    hidden_size: int = 4096
    intermediate_size: int = 12288
    moe_intermediate_size: int = 2048
    num_hidden_layers: int = 36
    num_attention_heads: int = 32
    num_key_value_heads: int = 32
    n_shared_experts: int = 1
    n_routed_experts: int = 128
    routed_scaling_factor: float = 1.0
    kv_lora_rank: int = 256
    q_lora_rank: Optional[int] = 1024
    qk_rope_head_dim: int = 64
    v_head_dim: int = 128
    qk_nope_head_dim: int = 64
    n_group: int = 1
    topk_group: int = 1
    num_experts_per_tok: int = 4
    first_k_dense_replace: int = 0
    norm_topk_prob: bool = True
    hidden_act: str = "silu"
    max_position_embeddings: int = 1048576
    rms_norm_eps: float = 1e-6
    tie_word_embeddings: bool = False
    rope_parameters: Optional[Dict[str, float]] = None
    rope_interleave: bool = True
    attention_bias: bool = False

    def __post_init__(self):
        if self.num_key_value_heads is None:
            self.num_key_value_heads = self.num_attention_heads
        self.qk_head_dim = self.qk_nope_head_dim + self.qk_rope_head_dim
        self.head_dim = self.qk_head_dim


def _get_llama_4_attn_scale(size, offset, beta: float, max_position_embeddings: int):
    if isinstance(offset, mx.array) and offset.ndim > 0:
        offset = offset[:, None]

    scaling = 1 + beta * mx.log(
        1 + mx.floor((mx.arange(size) + offset) / max_position_embeddings)
    )
    if scaling.ndim == 2:
        return scaling[:, None, :, None]
    return scaling[:, None]


def _route_tokens_to_experts(
    router_logits: mx.array,
    top_k: int,
    n_group: int,
    topk_group: int,
    routed_scaling_factor: float,
    norm_topk_prob: bool,
) -> tuple[mx.array, mx.array]:
    scores = mx.softmax(router_logits.astype(mx.float32), axis=-1)

    if n_group > 1:
        grouped = mx.unflatten(scores, axis=-1, shape=(n_group, -1))
        group_scores = mx.topk(grouped, 2, axis=-1).sum(axis=-1)
        group_idx = mx.argpartition(-group_scores, kth=topk_group - 1, axis=-1)[
            ..., :topk_group
        ]
        group_mask = mx.zeros_like(group_scores)
        group_mask = mx.put_along_axis(group_mask, group_idx, mx.array(1.0), axis=-1)
        score_mask = mx.broadcast_to(group_mask[..., None], grouped.shape).reshape(
            scores.shape
        )
        scores_for_choice = mx.where(score_mask > 0, scores, mx.array(0.0, scores.dtype))
    else:
        scores_for_choice = scores

    inds = mx.argpartition(-scores_for_choice, kth=top_k - 1, axis=-1)[..., :top_k]
    topk_weights = mx.take_along_axis(scores, inds, axis=-1)
    if top_k > 1 and norm_topk_prob:
        topk_weights = topk_weights / (
            topk_weights.sum(axis=-1, keepdims=True) + mx.array(1e-20, topk_weights.dtype)
        )
    topk_weights = topk_weights * routed_scaling_factor
    return inds, topk_weights


class MLP(nn.Module):
    def __init__(self, config: ModelArgs, intermediate_size: Optional[int] = None):
        super().__init__()
        hidden_dim = (
            config.intermediate_size if intermediate_size is None else intermediate_size
        )
        self.gate_proj = nn.Linear(config.hidden_size, hidden_dim, bias=False)
        self.up_proj = nn.Linear(config.hidden_size, hidden_dim, bias=False)
        self.down_proj = nn.Linear(hidden_dim, config.hidden_size, bias=False)

    def __call__(self, x: mx.array) -> mx.array:
        return self.down_proj(swiglu(self.gate_proj(x), self.up_proj(x)))


class Attention(nn.Module):
    def __init__(self, config: ModelArgs):
        super().__init__()
        self.num_heads = config.num_attention_heads
        self.num_key_value_heads = config.num_key_value_heads
        self.hidden_size = config.hidden_size
        self.q_lora_rank = config.q_lora_rank
        self.qk_rope_head_dim = config.qk_rope_head_dim
        self.kv_lora_rank = config.kv_lora_rank
        self.v_head_dim = config.v_head_dim
        self.qk_nope_head_dim = config.qk_nope_head_dim
        self.qk_head_dim = config.qk_head_dim
        self.scale = self.qk_head_dim**-0.5

        if self.q_lora_rank is None:
            self.q_proj = nn.Linear(
                config.hidden_size,
                self.num_heads * self.qk_head_dim,
                bias=False,
            )
        else:
            self.q_a_proj = nn.Linear(
                config.hidden_size, config.q_lora_rank, bias=config.attention_bias
            )
            self.q_a_layernorm = nn.RMSNorm(config.q_lora_rank, eps=config.rms_norm_eps)
            self.q_b_proj = nn.Linear(
                config.q_lora_rank,
                self.num_heads * self.qk_head_dim,
                bias=False,
            )

        self.kv_a_proj_with_mqa = nn.Linear(
            config.hidden_size,
            self.kv_lora_rank + self.qk_rope_head_dim,
            bias=config.attention_bias,
        )
        self.kv_a_layernorm = nn.RMSNorm(config.kv_lora_rank, eps=config.rms_norm_eps)
        self.kv_b_proj = nn.Linear(
            config.kv_lora_rank,
            self.num_heads * (self.qk_nope_head_dim + self.v_head_dim),
            bias=False,
        )
        self.o_proj = nn.Linear(
            self.num_heads * self.v_head_dim,
            config.hidden_size,
            bias=config.attention_bias,
        )
        self.rope = initialize_rope(
            dims=self.qk_rope_head_dim,
            base=config.rope_parameters["rope_theta"],
            traditional=config.rope_interleave,
            scaling_config=config.rope_parameters,
            max_position_embeddings=config.max_position_embeddings,
        )
        self.rope_beta = config.rope_parameters["llama_4_scaling_beta"]
        self.original_max_position_embeddings = config.rope_parameters[
            "original_max_position_embeddings"
        ]

    def __call__(
        self,
        x: mx.array,
        attn_scale: mx.array,
        mask: Optional[mx.array] = None,
        cache: Optional[Any] = None,
    ) -> mx.array:
        batch_size, seq_length, _ = x.shape
        query_shape = (batch_size, seq_length, self.num_heads, self.qk_head_dim)
        kv_shape = (
            batch_size,
            seq_length,
            self.num_heads,
            self.qk_nope_head_dim + self.v_head_dim,
        )

        if self.q_lora_rank is None:
            q_states = self.q_proj(x)
        else:
            q_states = self.q_b_proj(self.q_a_layernorm(self.q_a_proj(x)))
        q_states = q_states.reshape(query_shape).transpose(0, 2, 1, 3)
        q_pass, q_rot = mx.split(q_states, [self.qk_nope_head_dim], axis=-1)

        compressed_kv = self.kv_a_proj_with_mqa(x)
        k_pass, k_rot = mx.split(compressed_kv, [self.kv_lora_rank], axis=-1)
        k_pass = (
            self.kv_b_proj(self.kv_a_layernorm(k_pass))
            .reshape(kv_shape)
            .transpose(0, 2, 1, 3)
        )
        k_pass, value_states = mx.split(k_pass, [self.qk_nope_head_dim], axis=-1)
        k_rot = k_rot.reshape(batch_size, 1, seq_length, self.qk_rope_head_dim)

        offset = cache.offset if cache is not None else 0
        q_rot = self.rope(q_rot, offset=offset)
        k_rot = self.rope(k_rot, offset=offset)
        k_rot = mx.broadcast_to(k_rot, k_pass.shape)

        query_states = mx.concatenate([q_pass, q_rot], axis=-1)
        key_states = mx.concatenate([k_pass, k_rot], axis=-1)
        query_states = query_states * attn_scale

        if cache is not None:
            key_states, value_states = cache.update_and_fetch(key_states, value_states)

        attn_output = scaled_dot_product_attention(
            query_states,
            key_states,
            value_states,
            cache=cache,
            scale=self.scale,
            mask=mask,
        )
        attn_output = attn_output.transpose(0, 2, 1, 3).reshape(batch_size, seq_length, -1)
        return self.o_proj(attn_output)


class Mistral4MoE(nn.Module):
    def __init__(self, config: ModelArgs):
        super().__init__()
        self.config = config
        self.switch_mlp = SwitchGLU(
            config.hidden_size,
            config.moe_intermediate_size,
            config.n_routed_experts,
            bias=False,
        )
        self.gate = nn.Linear(config.hidden_size, config.n_routed_experts, bias=False)
        self.shared_experts = MLP(
            config,
            intermediate_size=config.moe_intermediate_size * config.n_shared_experts,
        )

    def __call__(self, x: mx.array) -> mx.array:
        residual = x
        topk_indices, topk_weights = _route_tokens_to_experts(
            self.gate(x),
            top_k=self.config.num_experts_per_tok,
            n_group=self.config.n_group,
            topk_group=self.config.topk_group,
            routed_scaling_factor=self.config.routed_scaling_factor,
            norm_topk_prob=self.config.norm_topk_prob,
        )
        routed = self.switch_mlp(x, topk_indices)
        routed = (routed * topk_weights[..., None]).sum(axis=-2)
        return routed + self.shared_experts(residual)


class DecoderLayer(nn.Module):
    def __init__(self, config: ModelArgs, layer_idx: int):
        super().__init__()
        self.self_attn = Attention(config)
        self.mlp = (
            Mistral4MoE(config)
            if layer_idx >= config.first_k_dense_replace
            else MLP(config)
        )
        self.input_layernorm = nn.RMSNorm(config.hidden_size, eps=config.rms_norm_eps)
        self.post_attention_layernorm = nn.RMSNorm(
            config.hidden_size, eps=config.rms_norm_eps
        )

    def __call__(
        self,
        x: mx.array,
        attn_scale: mx.array,
        mask: Optional[mx.array] = None,
        cache: Optional[Any] = None,
    ) -> mx.array:
        r = self.self_attn(self.input_layernorm(x), attn_scale, mask, cache)
        h = x + r
        r = self.mlp(self.post_attention_layernorm(h))
        return h + r


class LanguageModel(PipelineMixin, nn.Module):
    def __init__(self, config: ModelArgs):
        super().__init__()
        self.args = config
        self.embed_tokens = nn.Embedding(config.vocab_size, config.hidden_size)
        self.layers = [
            DecoderLayer(config, layer_idx)
            for layer_idx in range(config.num_hidden_layers)
        ]
        self.norm = nn.RMSNorm(config.hidden_size, eps=config.rms_norm_eps)

    def __call__(
        self,
        inputs: mx.array,
        cache=None,
        input_embeddings: Optional[mx.array] = None,
    ) -> mx.array:
        h = input_embeddings if input_embeddings is not None else self.embed_tokens(inputs)

        pipeline_rank = self.pipeline_rank
        pipeline_size = self.pipeline_size

        if cache is None:
            cache = [None] * len(self.pipeline_layers)
            offset = 0
        else:
            offset = cache[0].offset

        mask = create_attention_mask(h, cache[0])
        attn_scale = _get_llama_4_attn_scale(
            inputs.shape[1],
            offset,
            self.args.rope_parameters["llama_4_scaling_beta"],
            self.args.rope_parameters["original_max_position_embeddings"],
        ).astype(h.dtype)

        if pipeline_rank < pipeline_size - 1:
            h = mx.distributed.recv_like(h, (pipeline_rank + 1))

        for layer, layer_cache in zip(self.pipeline_layers, cache):
            h = layer(h, attn_scale, mask, cache=layer_cache)

        if pipeline_rank != 0:
            h = mx.distributed.send(h, (pipeline_rank - 1) % pipeline_size)
            if cache[-1] is not None:
                cache[-1].keys = mx.depends(cache[-1].keys, h)

        if pipeline_size > 1:
            h = mx.distributed.all_gather(h)[: h.shape[0]]

        return self.norm(h)


class Model(nn.Module):
    def __init__(self, args: ModelArgs):
        super().__init__()
        self.args = args
        self.model_type = args.model_type
        self.model = LanguageModel(args)
        if not args.tie_word_embeddings:
            self.lm_head = nn.Linear(args.hidden_size, args.vocab_size, bias=False)

    def __call__(
        self,
        inputs: mx.array,
        cache=None,
        input_embeddings: Optional[mx.array] = None,
    ):
        out = self.model(inputs, cache, input_embeddings)
        if hasattr(self, "lm_head"):
            return self.lm_head(out)
        if hasattr(self.model.embed_tokens, "as_linear"):
            return self.model.embed_tokens.as_linear(out)
        return out @ self.model.embed_tokens.weight.T

    def sanitize(self, weights):
        return {
            k: v
            for k, v in weights.items()
            if "vision_tower" not in k
            and "multi_modal_projector" not in k
            and "activation_scale" not in k
            and "scale_inv" not in k
            and "rotary_emb.inv_freq" not in k
        }

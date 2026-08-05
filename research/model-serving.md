# Model Serving & Fast Swap for Home GPUs — Research Findings

> **Status:** Research (mid-2026) · **Project:** wordslab-platform (home-scale, 100% OSS local AI platform)
> **Question:** How do OSS model servers handle running many AI services on GPUs that can't hold them all at once — RAM-resident weights, fast load/unload, hot-swapping models on demand?
> **Related:** `platform-studies/gpu/summary.md`, `platform-studies/architecture.md` (L1), `platform-studies/text/summary.md`

---

## 1. TL;DR — recommendations

1. **Base the platform's model layer on Ollama (MIT).** Ollama *is* already a model manager: it loads GGUF models via llama.cpp, keeps idle models in memory for a configurable window (`keep_alive`, default 5 min), unloads to make room, loads multiple models concurrently when memory allows, and evaluates VRAM across multiple GPUs. The platform should orchestrate it, not reimplement it.
2. **Use llama.cpp / llama-server directly where fine control matters** (MIT): memory-mapped weights (mmap) mean a model's weights can be *resident in RAM* and only the touched pages/offloaded layers occupy VRAM — exactly the "weights cached in RAM, loaded/unloaded quickly on demand" requirement. Its **RPC backend pipeline-parallelizes one GGUF model across machines** — the multi-machine story for big models.
3. **vLLM is optional, not default** (Apache-2.0): excellent for high concurrency and KV-cache CPU offload, but heavy, and its weights always instantiate in GPU memory first (OOM risk) — wrong tool for home hot-swapping. Reserve it for heavy deployments (e.g. the 2×96 GB enterprise case).
4. **GGUF Q4_K_M is the default format.** It is the community sweet spot (~95–97% quality, 4.8 bits/weight) and the one format all of Ollama/llama.cpp/LM Studio speak natively.
5. **The platform's "model manager" is a thin orchestration layer**, not a serving engine: per-service model mapping, inference policy (local/cloud), RAM-pinned model list, GPU budget across services, preload/warm hints, and (later) RPC placement across machines.

---

## 2. Hardware reality (what fits where)

All figures are for inference with ~8K context, Q4_K_M weights (the default recommendation). VRAM includes weights + KV cache + runtime overhead.

| Model size | File (Q4_K_M) | VRAM needed | Fits on |
|---|---|---|---|
| 7–8 B | ~4.5 GB | ~6–7 GB | **RTX 3070 8 GB** (small chat, embeddings) |
| 12–14 B | ~9 GB | ~10–11 GB | 4090/5090 comfortably; 8 GB card: no |
| 27–32 B | ~20 GB | ~22–24 GB | **RTX 4090 24 GB** (Q4, 4–8K ctx); **RTX 5090 32 GB** (Q5–Q8) |
| 70–72 B | ~42 GB | ~45+ GB | needs 2×24 GB, 48 GB+, or partial CPU/RAM offload; 5090 32 GB cannot hold it alone |

Key numbers for the user's machines:
- **RTX 3070 8 GB / 32 GB RAM** — 7–8B Q4 models; also fine for small embedding/STT/TTS models.
- **RTX 4090 24 GB / 32 GB RAM** — the natural home for a 32B Q4 chat/agent model.
- **RTX 5090 32 GB / 64 GB RAM** — 32B at Q5–Q8; a 70B only via RAM offload (slow) or by splitting across machines (RPC).
- **2× RTX 6000 Pro 96 GB** — any 70B at Q4–Q5 fully in VRAM, plus headroom for many concurrent services.

**KV cache is the silent VRAM eater:** an 8B model at 32K context needs ~4.5–5 GB of KV cache alone (70B at 128K: 42 GB+). Levers: lower context, or KV cache quantization (`OLLAMA_KV_CACHE_TYPE=q8_0/q4_0` in Ollama; `--cache-type-k/v` in llama.cpp) which roughly halves it with modest quality loss.

---

## 3. Engine-by-engine

### Ollama — MIT, the default choice
- **Memory management is built in**: `keep_alive` parameter on `/api/generate` and `/api/chat` (`-1` = keep loaded forever, `0` = unload immediately, `N` = N seconds); `OLLAMA_KEEP_ALIVE` env var sets the default (5 min).
- **Concurrency**: if memory suffices, multiple models stay loaded at once; as models go idle, Ollama evicts them to make room for new ones.
- **Multi-GPU**: on load, it evaluates required VRAM against what's available across GPUs.
- **`ollama stop <model>`** unloads on demand. Preload a model with `keep_alive=-1` for fast first response.
- **Limitations**: no fine-grained layer placement, no cross-machine serving, RAM-residency of *all* weights not directly exposed (it can keep models in RAM but the platform can't pin arbitrary models). API is OpenAI-compatible.

### llama.cpp / llama-server — MIT, the fine-control engine
- **mmap weight loading**: GGUF weights are memory-mapped. Pages are faulted in on demand — a model "in RAM" costs nothing until touched, and `POSIX_MADV_WILLNEED` prefetches at load. This is the closest thing to the requested "weights cached in RAM" primitive: the OS page cache *is* the weight cache.
- **Partial GPU offload**: `-ngl N` puts N layers on GPU, rest stay in RAM; `--no-kv-offload` keeps KV cache on CPU; KV cache quantization via `--cache-type-k/v`.
- **RPC backend (distributed)**: pipeline-parallelizes any GGUF model across machines — `-ngl 99` distributes layers across the local GPU + remote `llama-server --rpc` nodes based on available VRAM, with layer-aware split for heterogeneous GPUs (mixed quantization supported). **This is how one big model runs across the 3 gaming PCs** (cf. exo below, which is Apple-focused).
- **llama-server** exposes an OpenAI-compatible HTTP API, multiple model slots, and is the right binary to wrap for a custom model manager.

### vLLM — Apache-2.0, optional for heavy serving
- PagedAttention + continuous batching; excellent at *many concurrent requests*.
- **KV cache CPU offload** is now native (0.11 "KV offloading connector", plus LMCache integration) and there is a **sleep mode** (L1: weights offloaded to CPU with CUDA graphs preserved for quick wake; L2: full discard, cold reload).
- **But**: weights are always instantiated in GPU memory first (OOM risk on small cards), CPU offloading carries a measurable throughput tax, and the operator burden (engine args, profiling) is real. Verdict: not the hot-swap tool; consider only where a single service needs high concurrency on a big GPU (the 2×96 GB enterprise case) or batch workloads.

### LM Studio — GUI reference, not a platform component
Polished model browser/manager, GGUF-only, splits models across GPU and RAM, hot-swaps models, OpenAI-compatible local server. **Proprietary** — use its UX as the design reference for the platform's model UI, not as a dependency.

### LocalAI — MIT, alternative gateway
OpenAI-compatible server with a model gallery and multiple backends (llama.cpp, vLLM, etc.). If the platform ever wants a single gateway process that is not Ollama, this is the candidate — but Ollama covers the common case with less moving parts.

### exo — Apache-2.0, inspiration for distributed inference
P2P cluster that shards one model across devices (each device holds a contiguous set of layers; activations ~8–32 KB passed over the network, <5 ms on LAN). Built on mlx/tinygrad with an Apple Silicon focus; **llama.cpp sharding is explicitly not supported** (its API is too high-level, exo issue #167). Conclusion: exo is not a fit for a Windows/WSL NVIDIA fleet — **llama.cpp RPC is the NVIDIA-viable equivalent** and the one to design for.

### TensorRT-LLM — not for v1
Engine compilation and cold-start costs make it wrong for on-demand hot-swapping at home scale. (Already well covered in the studies' L1 section; revisit only if a service needs peak single-model performance.)

---

## 4. Load/unload times — what to expect

Ballpark, based on mechanism (NVMe ~3–7 GB/s; PCIe 4.0 x16 ~28 GB/s; RAM >30 GB/s):

| Model (Q4_K_M) | Size | Cold from disk (NVMe) | From RAM/page cache → GPU |
|---|---|---|---|
| 8 B | ~4.5 GB | ~1–2 s | <0.5 s |
| 14 B | ~9 GB | ~2–3 s | ~0.5 s |
| 32 B | ~20 GB | ~3–6 s | ~1 s |
| 70 B | ~42 GB | ~8–12 s | ~1.5–2 s |

Takeaways:
- With mmap/Ollama, the **first** load reads from disk; the **second** load of the same model is served from the OS page cache/RAM — near-instant for small models, ~1 s even for a 32B.
- The dominant cost of "switching services" is therefore **VRAM contention, not disk reads**: two services whose models overlap in RAM can swap in ~1 s each.
- Design implication: the model manager should keep the *working set* of models warm in RAM (Ollama `keep_alive=-1` on pinned models, or llama.cpp mmap residency) and treat GPU upload as the only per-switch cost.

---

## 5. What the platform's "model manager" should be

A thin orchestration layer (Python), not a serving engine:

1. **Per-machine Ollama (or llama-server) instance** managed as a platform service — the engine handles loading, caching, eviction.
2. **Model registry**: catalog of GGUF models per service (chat, embeddings, STT/TTS, image…), with size/VRAM metadata (read live, e.g. `ollama show --modelfile` / HF metadata), default Q4_K_M.
3. **GPU budget**: a simple per-machine table of what's loaded and what it costs in VRAM; the manager preloads/unloads (Ollama `keep_alive` / `ollama stop`, or llama.cpp slots) based on service demand — the "smart weights caching in RAM" the product needs.
4. **Placement (multi-machine, later)**: per-service placement across machines (many small models) + llama.cpp RPC for one big model across machines (e.g. a 70B split over the 4090 + 5090).
5. **Cloud fallback decision point**: if the local model is absent or the machine is underpowered, the per-service inference policy (`local-only` / `local-then-cloud` / `cloud-only`, from the cloud-fallback research) decides — the manager is where that policy is evaluated.
6. **What must be custom-built**: the orchestration + policy + UI — none of the engines provide the "many services, one GPU, swap on demand" platform view.

---

## 6. Licensing

Ollama MIT · llama.cpp MIT · vLLM Apache-2.0 · LocalAI MIT · exo Apache-2.0 · LM Studio **proprietary** (UX reference only) · TensorRT-LLM NVIDIA license (optional, not v1). No AGPL blockers in the recommended path.

---

## 7. Sources

- Ollama FAQ (keep_alive, concurrency, multi-GPU): https://docs.ollama.com/faq
- Ollama keep_alive discussion & behavior: https://github.com/ollama/ollama/issues/1600
- llama.cpp guide (quantization table, offload, VRAM): https://steelph0enix.github.io/posts/llama-cpp-guide/
- llama.cpp mmap / page behavior (HN): https://news.ycombinator.com/item?id=49130892
- llama.cpp MoE two-tier GPU+RAM cache (feature request): https://github.com/ggml-org/llama.cpp/issues/20757
- vLLM KV offloading connector (0.11): https://vllm.ai/blog/2026-01-08-kv-offloading-connector
- vLLM CPU-offload caveats: https://www.reddit.com/r/Vllm/comments/1onqfx7/the_35x_performance_tax_vllms_cpu_offloading_is_a/
- vLLM sleep mode: https://blog.vllm.ai/2025/10/26/sleep-mode.html
- LMCache CPU offload with vLLM: https://docs.lmcache.ai/getting_started/quickstart/offload_kv_cache.html
- Distributed inference options (llama.cpp RPC vs exo): https://localaimaster.com/blog/distributed-inference-local-ai
- exo — P2P inference clustering (layer partitioning, activations): https://news.ycombinator.com/item?id=40973339 · https://github.com/exo-explore/exo
- exo llama.cpp engine (not supported): https://github.com/exo-explore/exo/issues/167
- Model size / VRAM tables (7B–70B, quants): https://localaimaster.com/blog/ai-model-size-comparison · https://www.sitepoint.com/vram-requirements-70b-models-16gb-gpu-minimum-2026/
- Ollama VRAM requirements (models, KV cache): https://localllm.in/blog/ollama-vram-requirements-for-local-llms
- GGUF quant cheat sheet: https://d-central.tech/quantization-explained-gguf-q4-q8-fp16/
- Local LLM hosting guide (LM Studio, LocalAI, vLLM): https://medium.com/@rosgluk/local-llm-hosting-complete-2025-guide-ollama-vllm-localai-jan-lm-studio-more-f98136ce7e4a

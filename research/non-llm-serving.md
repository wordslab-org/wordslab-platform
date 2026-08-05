# Non-LLM Model Serving — Research Findings

> **Ticket:** Everything that is not an autoregressive LLM: diffusion image/video, embeddings/rerank, STT/TTS, classic PyTorch/sklearn models.
> **Context:** wordslab-platform — Apache-2.0, 100% OSS, home-scale AI platform on gaming PCs (RTX 3070 8GB / 4090 24GB / 5090 32GB, 32–64GB RAM, Windows via WSL). Models are RAM-cached and load/unloaded on demand so services share a GPU. LLM serving (GGUF Q4_K_M via Ollama/llama.cpp/vLLM) is covered by a separate ticket.
> **Date of research:** August 2026.

---

## 1. Image generation (diffusion)

### Engine: ComfyUI (recommended) — with a thin OpenAI-compat bridge in front

- **License: GPL-3.0** (confirmed, Comfy-Org/ComfyUI). Runs as its own server process exposing an HTTP API: `POST /prompt` (submit workflow JSON), `/queue`, `/history`, and a WebSocket `/ws` for progress. It is **not** REST; the platform needs a bridge service that maps `/v1/images/*` onto workflow JSONs.
- **Load/cache behavior (critical for the model-manager story):**
  - Models are kept in VRAM until evicted by memory pressure or a clear-VRAM node; weights stay cached in **RAM** between runs by default (`--cache-ram`). Alternatives: `--cache-classic` (aggressive), `--cache-lru N` (keep N loaded results), `--cache-none` (no RAM caching).
  - VRAM tiers via CLI: `--normalvram` (default), `--lowvram`, `--novram`, `--highvram`, plus `--reserve-vram N` and `--disable-smart-memory`.
  - **Dynamic VRAM** (custom PyTorch allocator, stable since Mar 2026 on NVIDIA Windows/Linux): weights are mapped to uncommitted file-backed memory, "faulted" into VRAM at the millisecond they're needed, evicted via a watermark system, and re-read from disk on demand. Effectively no manual VRAM quota management; RAM use is OS-reclaimable. **Gotcha: WSL support "currently not planned"** — on the platform's WSL target, rely on `--lowvram`/`--normalvram` + cache flags instead.
  - Net: ComfyUI already implements exactly the "RAM-cached, load-on-demand" model the platform wants, internally. The platform's model manager should *configure* ComfyUI's cache/VRAM flags per machine, not reimplement weight management.
- **OpenAI-compatible bridges** (all are separate processes talking to ComfyUI's HTTP API — see license note below):
  - **comfyui2api** (Einzieg, MIT, Python, active 2026): wraps ComfyUI as an OpenAI-compatible service; txt2img / img2img / txt2video / img2video from exported workflow JSONs; job lifecycle `pending→queued→running→completed/failed`; WebSocket progress passthrough; works with New-Api gateways; WSL-friendly (uploads via ComfyUI's HTTP interface). Good starting point or reference for a custom bridge.
  - **Salad comfyui-api** (MIT, TypeScript): generic workflow API in front of `/prompt`.
  - **comfy2go** (MIT, Go, inactive). **Avoid** `stable-diffusion-api-to-openai` (AGPL).
  - **Build-your-own** is ~1 thin FastAPI service (platform's Track T6b already plans this): submit workflow, poll `/history`, stream WS progress. This is the recommended path to guarantee the platform's S.* conventions (auth, errors, async job model) rather than adopting a third-party bridge wholesale.
- **Lighter alternative — Diffusers + FastAPI** (diffusers is Apache-2.0): `FastFusion` (HanseWare) and `Aquiles-Image` both expose OpenAI-compatible `/v1/images/generations` over diffusers AutoPipelines; also `imageRouter`-style services. Better when you need only 1–2 fixed pipelines and full control; no node graphs, no LoRA/ControlNet ecosystem depth.

### Model sizes & VRAM (what fits where)

| Model (params) | File / VRAM at precision | 3070 8GB | 4090 24GB | 5090 32GB |
|---|---|---|---|---|
| **FLUX.1-dev** (11.9B) | FP16 ~23.8GB file, ~24–33GB VRAM; FP8 ~11.9GB, ~12–16GB; GGUF Q4_K_S ~6.8GB, ~6–8GB; Q5 ~8.3GB; Q6 ~9.9GB. T5-XXL encoder ~9.2GB fp16 → use FP8 T5 (−4–5GB) | GGUF Q4 + `--lowvram` (slow, usable) | FP8 (fast) or FP16 (tight) | FP16 + batch |
| **FLUX.1-schnell** (11.9B) | same weights, 4-step, min ~10GB | Q4/FP8 w/ offload | full | full |
| **SDXL** (3.5B) | ~6.5–7GB fp16; 3–5s @ 20 steps on 4090 | ✅ comfortable | ✅ | ✅ |
| **SD 3.5 Medium** (2B) | ~6GB VRAM | ✅ | ✅ | ✅ |
| **SD 3.5 Large** (8B) | UNet ~10GB fp16; total 16–18GB with triple text-encoder; FP8 ~12–14GB | ❌ (offload only) | ✅ FP16 tight / FP8 comfy | ✅ |
| **SD 1.5** (0.86B) | 4–5GB | ✅ | ✅ | ✅ |

**Tier takeaways:** 8GB = SDXL family, SD3.5-Medium, FLUX Q4 (experiment-grade); 24GB = FLUX FP8 sweet spot + SD3.5-Large; 32GB = FLUX FP16 + addon stacks + batches.

### Image-model licenses (important — several flagship checkpoints are **non-commercial**)

- FLUX.1-**schnell**: Apache-2.0 ✅ · FLUX.1-**dev**: BFL non-commercial license ❌
- SDXL, SD3.5: Stability AI Community License (non-commercial) ❌ · SD1.5: CreativeML Open RAIL-M ✅ (commercial allowed)
- **Recommendation:** default image stack = FLUX.1-schnell (commercial-safe quality) with optional SDXL/FLUX-dev/SD3.5 gated behind a user license-acceptance flag (mirrors how the platform should handle any non-permissive weight).

---

## 2. Video generation (diffusion)

No mature OpenAI-compatible local video API exists; **video must be a custom async job service** (`/v1/videos/*` submit → poll → webhook), fronting ComfyUI workflows (comfyui2api already does txt2video/img2video via workflow JSONs).

| Model | Weights / VRAM | GPU fit | License |
|---|---|---|---|
| **Wan 2.2 14B** | FP16 54–65GB; **FP8 ~22–26GB @720p** | 4090/5090 (FP8); 8GB only via heavy quant + offload | Apache-2.0 ✅ |
| **Wan 2.2 5B** | FP16 ~18–28GB; ~8–12GB FP8 | 8GB (quant), 24GB full | Apache-2.0 ✅ |
| **LTX-Video / LTX-2.3** | LTX 0.9.5 fits 12GB; LTX-2.3 FP8 ~22–23GB | fastest on 12–24GB | Apache-2.0 ✅ |
| **HunyuanVideo** (13B) | 60–80GB @720p | ❌ home GPUs | Tencent non-commercial ❌ |

Generation is slow (minutes per 5s clip on consumer GPUs) → **async job queue is mandatory**; never block HTTP on video gen.

---

## 3. Embeddings & rerank

**Engine: HuggingFace TEI (text-embeddings-inference), Apache-2.0.** OpenAI-compatible out of the box: `POST /v1/embeddings` (plus native `/embed`, `/rerank`, `/decode`). Serves both embedding and cross-encoder rerank models from one container.

| Model | Params / size | VRAM | Notes |
|---|---|---|---|
| bge-m3 | 0.6B, ~2.3GB file | ~2.5GB | multilingual, 8K ctx, 1024 dims |
| Qwen3-Embedding-0.6B | 0.6B, 639MB GGUF / ~1.2GB fp32 | ~2GB | 32K ctx, 1024 dims, best MTEB/GB (2026) |
| mxbai-embed-large | 0.3B, ~670MB | ~1GB | English, 512 ctx |
| bge-reranker-v2-m3 | ~2.3GB | ~2.5GB | multilingual rerank |
| mxbai-rerank-large-v2 | ~1.1GB | ~1.5GB | English rerank, 8K ctx |

All Apache-2.0 ✅. **These are GB-scale at most → always resident; no VRAM management needed.** Alternatives: **fastembed** (Apache-2.0, ONNX, in-process CPU — zero server) or sentence-transformers + FastAPI. Note Jina reranker v2 is CC-BY-NC (avoid). Recommendation: TEI as the shared embed/rerank service (it's already in the platform's core stack); fastembed as the in-process fallback.

---

## 4. Speech-to-Text

**Engine: faster-whisper (MIT, CTranslate2).** Sizes (model → params → VRAM): tiny ~39M/~0.1GB; base 74M/~0.15GB (int8); small 244M/~0.5GB; medium 769M/~1.5GB; **large-v3 1.55B / ~3GB int8 or ~6GB fp16**; **large-v3-turbo 809M / ~1.6GB int8** (best for realtime). Batch + chunked streaming both supported; Whisper weights are MIT.

- **OpenAI-compatible servers:** **speaches** (Apache-2.0) — `/v1/audio/transcriptions` + translations, SSE streaming, live/realtime mode, Docker; **faster-whisper-server** (mcfletch); **whisper-asr-webservice** (ahmetoner). All drop-in for OpenAI SDKs.
- **whisper.cpp (MIT)** — GGML quantized, smallest footprint, great for CPU-only fallback.
- **Parakeet TDT 0.6B v2 / v3** (NVIDIA, **CC-BY-4.0** ✅) — 0.6B, extremely fast English ASR; good alternative for English-only high-throughput.
- **VRAM fit:** large-v3 int8 (~3GB) is resident-viable on all target GPUs; recommend one resident int8 STT model + a resident Kokoro, i.e. voice needs no load/unload management either. Realtime voice agents (Pipecat/LiveKit) are covered by the platform's T6c.

---

## 5. Text-to-Speech

| Model | Size / VRAM | Streaming | License |
|---|---|---|---|
| **Kokoro-82M** | 82M, ~0.35GB fp32, <2GB VRAM, **CPU real-time** | yes (chunked) | Apache-2.0 ✅ |
| **Piper** | per-voice ONNX 20–200MB, CPU real-time (RPi-class) | yes | MIT (original; a GPL-3.0 fork now exists — verify at pin) ✅/⚠️ |
| **XTTS-v2** | ~467M, ~2GB weights, 4–6GB VRAM real-time; zero-shot cloning | yes | **CPML non-commercial** ❌ (Coqui shut down Jan 2024; no commercial license obtainable) |
| **CosyVoice2** | ~0.5B, ~2–4GB VRAM; streaming + zero-shot cloning | yes | Apache-2.0 ✅ |

- **OpenAI-compatible:** **Kokoro-FastAPI** (Apache-2.0) exposes `/v1/audio/speech` (+ `/v1/audio/voices`) with streaming, mp3/wav/opus/flac/pcm, CPU+GPU Docker images — the ready-made default TTS surface. Piper has similar wrappers.
- **Recommendation:** default TTS = Kokoro (commercial-safe, tiny, resident); voice cloning = CosyVoice2 (Apache-2.0) instead of XTTS-v2 (non-commercial). Flag XTTS-v2 and F5-TTS (CC-BY-NC weights) as optional user-accepted models only.

---

## 6. Classic models (PyTorch / sklearn / ONNX) + NLP

For a home platform the **simplest thing wins**: plain **FastAPI + joblib** for sklearn, **ONNX Runtime** (MIT) for converted PyTorch/sklearn models, served as per-service endpoints (platform's text-svc). Heavyweight platforms (BentoML, MLflow, Ray Serve — all Apache-2.0) add model stores, registries, and autoscaling that a single workstation doesn't need; BentoML is the one worth keeping in mind if the platform later wants a generic "bring your own model" runner with auto-OpenAPI from a `service.py`.

- **NLP/classification/NER:** **spaCy** (MIT, CPU, high-throughput pipelines) for deterministic NLP; **GLiNER** (Apache-2.0, small ~0.2–0.4GB models, zero-shot NER/classification with arbitrary labels) for open-vocabulary extraction — it ships a built-in `python -m gliner.serve` FastAPI server (not OpenAI-compat; trivially wrapped). GLiNER-v2.5 small/base run on CPU fine.
- **Recommendation:** a generic **"model runner"** FastAPI service with pluggable backends (joblib / ONNX / safetensors-torch) + a `predict`-style endpoint, used for user-uploaded sklearn/ONNX models; spaCy+GLiNER live inside text-svc as in-process libraries (no server needed).

---

## 7. Model-manager fit (per family)

| Family | Engine | OpenAI-compat | Formats | Resident vs managed | VRAM budget |
|---|---|---|---|---|---|
| LLM (other ticket) | Ollama/llama.cpp/vLLM | native | GGUF | managed (existing) | per-model |
| Image diffusion | ComfyUI + bridge | **bridge needed** (comfyui2api or custom; video likewise) | safetensors, GGUF, fp8 | **managed** — ComfyUI caches in RAM + faults to VRAM; set `--cache-*`/`--lowvram` per machine; WSL → no Dynamic VRAM, use classic flags | FLUX Q4 ≈8GB · FP8 ≈13GB · FP16 ≈26GB |
| Video diffusion | ComfyUI workflows, async | **custom async job API** | safetensors | **managed** (same as image) | Wan14B FP8 ≈22–26GB |
| Embeddings/rerank | TEI (or fastembed) | **native** `/v1/embeddings`, `/rerank` | safetensors | **resident** | ≤3GB total |
| STT | faster-whisper + speaches (or whisper.cpp) | **native** `/v1/audio/transcriptions` | CTranslate2, GGML | **resident** (large-v3 int8 ~3GB) | ~3GB |
| TTS | Kokoro (+Kokoro-FastAPI), CosyVoice2 | **native** `/v1/audio/speech` | safetensors/ONNX (Piper) | **resident** | ≤2GB (or CPU) |
| Classic/sklearn | FastAPI + joblib/ONNX Runtime | custom `predict` endpoints | joblib/pickle, ONNX | **resident** (CPU) | 0 (CPU) |
| NLP (NER/classify) | spaCy, GLiNER (in-process) | custom | pickled pipelines, safetensors | **resident** (CPU) | 0 (CPU) |

**What the platform model registry must know beyond GGUF LLMs:**
1. **Formats:** GGUF, safetensors (diffusion checkpoints + HF transformers), fp8 checkpoints, ONNX (Piper, classic, fastembed), CTranslate2 (faster-whisper), joblib/pickle (sklearn).
2. **Per-family VRAM budgets** (as above) so the scheduler can keep the resident set (embeddings + whisper int8 + Kokoro ≈ 6GB) always loaded and swap only diffusion models, respecting GPU headroom for the LLM.
3. **Engine affinity:** which engine serves which family (ComfyUI ↔ diffusion, TEI ↔ embeddings, speaches ↔ STT, Kokoro-FastAPI ↔ TTS, text-svc ↔ NLP/classic).
4. **License tagging per model:** commercial-safe (Apache/MIT/CC-BY/RAIL-M) vs non-commercial (FLUX-dev, SDXL/SD3.5, XTTS, HunyuanVideo, F5-TTS) — default catalog only permissive weights; non-commercial ones behind explicit acceptance.
5. **Download provenance:** HF Hub (all families), ComfyUI model registry; sizes drive disk planning (FLUX FP16 24GB + Wan 14B FP8 23GB + LLMs ≈ 100GB+ total — worth a disk budget line).

**Licensing summary (GPL/AGPL flags for an Apache-2.0 platform shipping separate services):**
- ComfyUI **GPL-3.0**, A1111 **AGPL-3.0**, SwarmUI **AGPL-3.0** — all fine as **separate processes** communicating over HTTP APIs (per GNU GPL FAQ: independent programs talking over normal interfaces are not derivative works; the ComfyUI maintainers' guidance says the same). Rules: never fork/embed ComfyUI code into the platform; **custom nodes in `custom_nodes/` are derivative → must stay GPL-3.0** (avoid shipping proprietary custom nodes); models/LoRAs carry their own licenses; the MIT bridge service stays MIT. Do not use A1111/SwarmUI (AGPL) when ComfyUI (GPL) + MIT bridge achieves the same.
- Everything else recommended here is permissive: TEI, fastembed, diffusers, faster-whisper, whisper.cpp, speaches, Kokoro(+server), CosyVoice2, GLiNER, spaCy, BentoML, MLflow, ONNX Runtime — Apache-2.0/MIT/CC-BY.
- Weights-license landmines to gate: FLUX.1-dev, SDXL, SD3.5 (Stability/ BFL non-commercial), XTTS-v2 (CPML), F5-TTS (CC-BY-NC), HunyuanVideo (Tencent non-commercial), Jina reranker v2 (CC-BY-NC).

---

## Recommendations (summary)

1. **Images:** ComfyUI (GPL, separate process) + a small custom MIT/FastAPI bridge exposing `/v1/images/generations|edits` and async `/v1/videos/*`; borrow comfyui2api's workflow-mapping approach. Let ComfyUI's own RAM-cache + Dynamic VRAM (or `--cache-lru`/`--lowvram` on WSL) do the load/unload.
2. **Default image models:** FLUX.1-schnell (Apache) and Wan/LTX (Apache) for video; offer FLUX-dev/SDXL/SD3.5 behind license acceptance.
3. **Embeddings/rerank:** TEI, resident. **STT:** faster-whisper large-v3 int8 via speaches, resident. **TTS:** Kokoro via Kokoro-FastAPI, resident; CosyVoice2 for cloning. **Classic/NLP:** FastAPI + joblib/ONNX + spaCy/GLiNER in-process.
4. **Model manager:** extend registry with the format list, per-family VRAM budgets, resident-set policy (≈6GB always-on; diffusion swapped on demand), engine affinity, and license tags; treat ComfyUI's flags as the diffusion knob.
5. **Hardware:** 8GB → SDXL/SD3.5-Medium + FLUX-Q4; 24GB → FLUX-FP8/Wan14B-FP8; 32GB → FLUX-FP16 + batches. Video gen is always async.

## Sources

- ComfyUI license (GPL-3.0): https://github.com/Comfy-Org/ComfyUI/blob/master/LICENSE · https://comfyui.org/en/comfyui-github
- GPL & aggregation guidance: https://github.com/Comfy-Org/ComfyUI/discussions/14346 · https://www.gnu.org/licenses/gpl-faq.html#GPLPlugins
- Dynamic VRAM (aimdo) + WSL note: https://blog.comfy.org/p/dynamic-vram-in-comfyui-saving-local
- ComfyUI startup flags (cache/VRAM): https://docs.comfy.org/development/comfyui-server/startup-flags · https://docs.comfy.org/troubleshooting/overview
- comfyui2api (MIT, OpenAI-compat bridge): https://github.com/Einzieg/comfyui2api · Salad comfyui-api: https://github.com/SaladTechnologies/comfyui-api
- FastFusion (diffusers OpenAI-compat): https://github.com/HanseWare/FastFusion · Aquiles-Image: https://github.com/Aquiles-ai/Aquiles-Image
- FLUX VRAM guide: https://localaimaster.com/blog/flux-vram-requirements-by-gpu · https://jarvislabs.ai/ai-faqs/best-gpu-for-flux · https://www.spheron.network/tools/gpu-recommender/black-forest-labs/FLUX.1-dev/
- Image VRAM guide 2026 (SDXL/SD3.5): https://willitrunai.com/blog/image-generation-vram-guide-2026 · SD3.5 ComfyUI: https://stable-diffusion-art.com/sd3-5-comfyui/
- Video VRAM (Wan/LTX/Hunyuan): https://willitrunai.com/blog/wan-2-2-vram-requirements · https://localaimaster.com/blog/local-ai-video-generation · https://www.spheron.network/blog/image-to-video-gpu-cloud-ltx-wan-hunyuan/
- TEI: https://github.com/huggingface/text-embeddings-inference · https://huggingface.co/docs/text-embeddings-inference/en/quick_tour · TEI VRAM table: https://www.spheron.network/blog/self-host-embedding-reranker-tei-gpu-cloud/
- Embedding model sizes: https://www.morphllm.com/ollama-embedding-models · https://huggingface.co/Qwen/Qwen3-Embedding-0.6B · reranker licenses: https://futureagi.com/blog/best-rerankers-for-rag-2026/
- faster-whisper: https://github.com/SYSTRAN/faster-whisper · VRAM/latency table: https://www.spheron.network/blog/faster-whisper-gpu-cloud-production-deployment-guide/ · https://www.promptquorum.com/power-local-llm/local-whisper-stt-comparison-2026
- speaches: https://github.com/speaches-ai/speaches · faster-whisper-server: https://github.com/mcfletch/faster-whisper-server
- Parakeet: https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2
- Kokoro: https://huggingface.co/hexgrad/Kokoro-82M · Kokoro-FastAPI: https://github.com/remsky/Kokoro-FastAPI · Kokoro vs Piper vs XTTS: https://localaimaster.com/blog/kokoro-tts-local-setup
- XTTS license (CPML non-commercial): https://huggingface.co/coqui/XTTS-v2/blob/main/LICENSE.txt · https://localaimaster.com/blog/xtts-coqui-commercial-license
- GLiNER serving: https://github.com/urchade/GLiNER · BentoML/MLflow local serving: https://docs.bentoml.com/en/latest/examples/mlflow.html

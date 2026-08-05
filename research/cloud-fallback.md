# Cloud Inference Fallback — Provider Survey & Abstraction Design

> **Status:** Research (mid-2026) · **Project:** wordslab-platform (home-scale, 100% OSS local AI platform)
> **Question:** Which cloud inference providers are viable as a *per-service* fallback when local hardware isn't enough, and how should the platform abstract "local or cloud" behind one API?
> **Related:** `platform-studies/gpu/summary.md`, `platform-studies/text/openrouter-api.md`, `platform-studies/text/openai-api.md`, `implementation.md` §1 (LiteLLM Proxy row).

---

## 1. TL;DR — recommendations

1. **Adopt OpenRouter as the single default cloud provider.** As of mid-2026 it serves every modality the platform needs — chat, embeddings, **image generation**, **STT and TTS**, even video — through one OpenAI-compatible base URL (`https://openrouter.ai/api/v1`), one API key, one bill, with model-level fallbacks and 25+ free models. One aggregator is *enough* for v1.
2. **Also support 2–4 direct providers as optional upstreams** (DeepInfra = cheapest, Groq = fastest, Cerebras = biggest free tier, Nebius = cheap + EU hosting). Same OpenAI-compatible surface, so the cost is just config. OpenRouter alone is not enough for latency-critical voice (routing overhead) or the absolute-lowest price per token.
3. **Abstraction: one internal OpenAI-compatible gateway = LiteLLM Proxy (MIT).** This matches the decision already recorded in `implementation.md` §1. It fronts local engines (Ollama, vLLM, llama.cpp) and every cloud provider behind one API, and natively provides the exact thing "per-service fallback" needs: fallback chains, context-window-aware fallback, retries/cooldowns, virtual keys per service, and cost tracking. A hand-written shim is only justified if the platform later decides zero-dependency-on-LiteLLM outweighs reimplementing fallback + cost accounting (~the hard 20% of the work).
4. **Each service declares its inference policy** (`local-only` / `local-then-cloud` / `cloud-only`) plus a privacy tier (`default` / `no-retention` / `no-training`). Cloud mode must surface *what leaves the machine* and default to OpenRouter's ZDR + `data_collection: deny` flags.
5. **Licensing:** LiteLLM is MIT (verified). Avoid AGPL components for anything the platform ships/distributes: Jan (AGPL-3.0), MinerU (AGPL-3.0), Firecrawl (AGPL-3.0). Open WebUI (BSD-3), Ollama (MIT), Portkey Gateway (MIT), one-api/new-api (MIT), Higress (Apache-2.0) are permissive alternatives.

---

## 2. Vocabulary (per wordslab CONTEXT.md)

- **Service** — a composable platform component (chat, image, voice, documents, agents…), each with its own DB, logic, UI, API.
- **Inference provider** — where a service's model runs: a local GPU machine, or a cloud API. *Each service chooses per deployment; cloud is the fallback when local hardware is insufficient.*

Design consequence: "local or cloud" is a **per-service configuration**, not a platform-wide toggle, and it must be swappable without changing service code. That is exactly what an OpenAI-compatible gateway in front of both local engines and cloud APIs gives you.

---

## 3. OpenRouter — the aggregator (default cloud provider)

- **One API, all modalities.** One base URL (`https://openrouter.ai/api/v1`), Bearer key, OpenAI-compatible. Dedicated endpoints: `/chat/completions`, `/embeddings`, `/images` (image gen, 30+ models, image-to-image), `/videos` (async), `/audio/speech` (TTS, OpenAI Audio API compatible), `/audio/transcriptions` (STT, base64 JSON or multipart ≤25 MB). Chat Completions is the stable primary surface; a stateless Responses API (`/v1/responses`) is in Beta.
- **Catalog & routing.** 300–400+ models from 60–70+ providers, all with a normalized OpenAI schema. Per-request `models[]` fallback array, provider ordering (`provider.order`), router slugs (`openrouter/auto`, `openrouter/free`, `:free` variants). Failed/fallback attempts are **not billed** — you pay only for the successful run.
- **Pricing.** Pay-per-token with prepaid credits; ~5.5% credit-purchase fee; BYOK (bring your own key) at ~5% fee after 1M free requests/month. `usage.cost` per response + `/api/v1/generation` stats = free cost attribution.
- **Free tier.** 25+ free models (Llama, Qwen, DeepSeek, Gemma… via `:free`). Limits: 20 req/min; 50 free-model requests/day under $10 of credits; **1,000/day once you hold ≥$10 in credits**. Fine for home experimentation and CI.
- **Latency/limits.** Adds a routing/normalization hop (~100–300 ms vs direct). Paid usage has per-model-tier platform rate limits; free variants have the tight caps. 429s carry `X-RateLimit-*` headers.
- **Privacy controls:** `provider.zdr: true` (Zero Data Retention endpoints only), `provider.data_collection: "deny"` (never route to providers that store/train on inputs), account-level training opt-out, sticky `session_id` routing, and an EU in-region endpoint (`https://eu.openrouter.ai`; guaranteed residency is Enterprise, but EU-headquartered providers can be pinned via `provider.order`).
- **Verdict:** the closest thing to "one API for every service's cloud mode". The OpenAI SDK is a drop-in via `base_url`.

---

## 4. Direct providers with OpenAI-compatible APIs

All use Bearer API keys and expose `/v1/chat/completions` (+ streaming); compatibility with the broader OpenAI surface varies. Prices are $/1M tokens (input/output), mid-2026, volatile — treat as ballpark.

| Provider | Chat models (open) | Embeddings | Images | STT/TTS | Free tier | Profile |
|---|---|---|---|---|---|---|
| **DeepInfra** | Llama, Qwen, DeepSeek, Mistral, GLM, Kimi (72 models) | ✅ Qwen3-Embedding-8B, bge | ✅ SD/FLUX via native API | ✅ Whisper | ❌ no free tier (postpaid; DeepStart for startups) | **Cheapest** per token on most models |
| **Together** | Llama 4, Qwen3, DeepSeek, GLM, Kimi (200+) | ✅ bge family | ✅ FLUX + Veo 3.0 (video) | ✅ Whisper | Historically $25 trial credits (reports vary in 2026) | Deepest catalog incl. image/video/audio; fine-tuning |
| **Fireworks** | 200+ open models, day-0 releases | ✅ from $0.008/M | ✅ FLUX, from $0.00013/step | ✅ Whisper $0.0009/min | $1 free credits | Best all-rounder; fast TTFT; full post-training stack |
| **Groq** | ~10: Llama 3.1/3.3/4, GPT-OSS, Qwen3 32B | ❌ none | ❌ | ✅ Whisper Large v3 + Orpheus TTS | ✅ no credit card; ~14.4k req/day; paid ~10× | **Fastest** (LPU, TTFT <300 ms, 500–3000 tok/s); narrow catalog, aggressive deprecations |
| **Nebius (AI Studio)** | 60+ open models (Qwen, Llama, DeepSeek, Kimi) | ✅ BAAI/bge-en-icl | ✅ FLUX from ~$0.0013/img | ✅ Whisper (OpenAI-compatible) | ~$1 trial credit (startup programs up to $5k) | Cheap, EU-based (Amsterdam/Paris datacenters) — good EU-residency story |
| **Hyperbolic** | DeepSeek, Llama, Qwen, Kimi | ✅ (some) | ✅ | ✅ | $1 credits; some free models without account; 60 req/min free | Discount aggregator; raw GPU rental too |
| **Cerebras** | 4: GPT-OSS 120B, Llama 3.1 8B, Qwen3 235B/32B, GLM 4.7 | ❌ none | ❌ | ❌ | ✅ **1M tokens/day free** (no CC) | Fastest tok/s (~2,600+); chat-only; tiny catalog |
| *Mistral / DeepSeek (first-party)* | Mistral models / DeepSeek V3.x | ✅ | ❌ | ❌ | Mistral has a free Experiment tier; DeepSeek none | Cheapest DeepSeek direct (~$0.27/$1.10 class) |

**Modality coverage for the platform's needs** (chat incl. vision = every provider above):

- **Embeddings:** OpenRouter (`/embeddings`), DeepInfra, Together, Nebius, Fireworks. **Not** Groq or Cerebras — cloud-embedding services must not pick these as sole provider.
- **Images:** OpenRouter (`/images`, 30+ models incl. FLUX), Together, Fireworks, Nebius, DeepInfra, Hyperbolic. Not Groq/Cerebras.
- **STT/TTS:** OpenRouter (`/audio/*`, OpenAI-compatible), Groq (Whisper + Orpheus), Fireworks, Together, DeepInfra, Nebius. Groq is the latency winner for realtime voice.
- **Video:** OpenRouter (async `/videos`), Together (Veo 3.0). Everything else: no.

**Latency profile (mid-2026 benchmarks):** Groq ≈ Cerebras fastest (hundreds–thousands tok/s, sub-300 ms TTFT); Fireworks < Together on TTFT (~0.34 s vs ~0.7–1.1 s) on the same Llama 3.3 70B, both ~83–90 tok/s; Nebius `-fast` endpoints target low TTFT; OpenRouter adds ~100–300 ms routing overhead; DeepInfra is price-first, throughput adequate. For realtime voice, direct Groq (or Groq via OpenRouter's `:nitro`-class routing) beats a generic direct provider.

---

## 5. Realistic cost table — main open models (per 1M tokens, input/output)

Mid-2026 snapshot from pricepertoken/morphllm aggregators + provider pages. Prices change monthly; the platform should read live prices from `GET /v1/models` (OpenRouter) rather than hardcoding.

| Model | DeepInfra | Fireworks | Together | Groq | Cerebras |
|---|---|---|---|---|---|
| Llama 3.1 8B | $0.02 / $0.04 | $0.20 / $0.20 | ~$0.10 / $0.15 | $0.05 / $0.08 | free tier / ~$0.10 / $0.30 |
| Llama 3.3 70B | $0.10 / $0.32 | $0.90 / $0.90 | ~$0.60 / $0.80 | — (Llama 3.3 70B) | — |
| Qwen3 32B | $0.08 / $0.28 | $0.90 / $0.90 | ~$0.12 / $0.30 | Qwen3 32B ✓ | ✓ free tier |
| Qwen3.5 9B | $0.10 / $0.15 | $0.20 / $0.20 | ~$0.10 / $0.15 | — | — |
| DeepSeek V4 Flash | $0.09 / $0.18 | $0.14 / $0.28 | ~$0.14 / $0.28 | — | — |
| DeepSeek V4 Pro | $1.30 / $2.60 | $1.74 / $3.48 | $2.10 / ~$3.40 | — | — |
| Mistral Small 24B | $0.05 / $0.08 | $0.90 / $0.90 | ~$0.10 / $0.30 | — | — |
| GPT-OSS 120B | $0.037 / $0.17 | $0.10 / $0.10 | ~$0.10 / $0.30 | $0.075 / $0.30 (20B) | ✓ |

Takeaways: **DeepInfra is cheapest on almost every model** (often 2–10× cheaper than Fireworks/Together); **Groq/Cerebras win on latency and free tier**; Together/Fireworks win on catalog breadth (fine-tuning, video, day-0 models). A home user doing a few thousand requests/month will spend **$0.00–$5/month** — cloud fallback is effectively free for light use. Heavy RAG embedding workloads are the cheapest cloud cost (embedding models at ~$0.008–0.05/M input) — still cheaper than a dedicated GPU for most homes.

---

## 6. The abstraction: LiteLLM Proxy vs a custom shim

**Recommendation: LiteLLM Proxy (MIT), consistent with `implementation.md` §1.** It is the only option that gives all of these out of the box:

- **One OpenAI-compatible API** (`http://localhost:4000/v1`) in front of local engines (Ollama, vLLM, llama.cpp, LM Studio) *and* cloud providers (OpenRouter, DeepInfra, Groq, Nebius, Cerebras, Together, Fireworks…).
- **Fallbacks:** `router_settings.fallbacks: [{local-model: [cloud-model]}]`, `context_window_fallbacks` (a 32k-token request that overflows the local 8k model automatically routes to cloud), retries, cooldowns, load balancing across deployments of the same model name.
- **Per-service isolation & cost attribution:** virtual keys per service/team → monthly spend limits → cost per key/team in Postgres, plus Langfuse/Prometheus callbacks (the platform already uses Langfuse).
- **Normalization:** `drop_params: true` silently drops parameters an upstream rejects — the #1 practical annoyance of multi-provider OpenAI compatibility (e.g. `top_k` on OpenAI models, `logit_bias` on Mistral).
- **Licensing:** MIT — no AGPL contamination; enterprise tier exists but core is permissive and self-hostable.

**Why not a custom shim?** A minimal FastAPI wrapper mapping `service config → base_url + api_key` is ~200 lines and tempting for "simplicity-first". But fallback chains, context-window-aware rerouting, retry/cooldown, streaming passthrough, `drop_params` normalization, and cost accounting are precisely the hard, boring 20% that LiteLLM already ships and tests. The platform's differentiator is services, not an inference router. Keep a **thin platform-owned layer on top** (the per-service `InferenceProvider` config + policy mapping to LiteLLM `model_list` entries) so LiteLLM remains a swappable implementation detail.

**Caveats:** LiteLLM is config- and dependency-heavy (Python app with many provider SDKs); pin versions; single-node fine at home scale (Redis only needed for multi-node). If a future constraint forbids LiteLLM, permissive drop-ins: Portkey Gateway (MIT), one-api/new-api (MIT), Higress (Apache-2.0). **Avoid AGPL components in anything distributed:** Jan (AGPL-3.0), MinerU (AGPL-3.0), Firecrawl (AGPL-3.0) — already flagged in the platform's risk register; workable for pure self-hosting, but conflicts with a clean OSS distribution story.

---

## 7. One aggregator, or direct providers too?

**v1: OpenRouter as the default; direct providers as optional, config-only additions.**

- *Why OpenRouter alone is nearly enough:* all four required modalities through one key; free models for experimentation; no per-provider contracts; automatic failover between upstream providers (it *is* the fallback layer, globally); billing/`usage.cost` built in; ZDR/EU controls.
- *Why direct providers still matter:*
  - **Latency:** realtime voice (STT/TTS) benefits from direct Groq (~100–300 ms less routing overhead); interactive chat from direct Cerebras/Groq.
  - **Cost:** DeepInfra is materially cheaper on the models a home user actually runs; OpenRouter prices mirror upstream + fees.
  - **Resilience & sovereignty:** a second cloud path independent of OpenRouter (e.g. Nebius for EU users); no single-point-of-dependency on one company.
  - **BYOK/no-margin cases:** some users will have existing keys (Mistral, DeepSeek, OpenRouter BYOK) — direct provider support makes those first-class.
- *What to build:* a provider registry in the platform (id, base_url, api_key ref, enabled modalities, privacy tier) that generates LiteLLM `model_list` + `fallbacks`. Adding a provider = adding a row, not code. OpenRouter ships pre-configured; DeepInfra, Groq, Cerebras, Nebius ship as templates.

---

## 8. How other local-AI products handle "local or cloud"

- **Open WebUI (BSD-3):** multiple provider *connections* (Ollama, OpenAI-compatible, OpenRouter, Anthropic…) configured side by side; per-model you choose the provider; a **Fallback Model** setting (Settings → Admin → AI → Models) routes to a default model when a custom model's assigned base is missing. It is per-chat/per-model selection, **not** automatic per-service failover.
- **LM Studio (proprietary, free):** local-first; **LM Link** connects remote machines; **"LM Studio Secure Cloud"** offers frontier open models as an opt-in cloud lane. No multi-provider auto-fallback.
- **Jan (AGPL-3.0):** local models and cloud providers (OpenAI, Nebius, etc.) coexist in one UI; you pick per conversation.
- **Pattern:** none of these do automatic local→cloud failover per service — they expose manual model/provider selection. The closest analogues are **OpenRouter-style model fallback** and **LiteLLM-style router fallback chains**. The platform is not copying a UI pattern; it makes cloud fallback a *service-level deployment policy*, which matches the CONTEXT.md definition of inference provider and is a small differentiator.

---

## 9. Privacy — what leaves the machine in cloud mode

When a service runs in cloud mode, **request payloads leave the machine**: user prompts, attached images/audio bytes, document excerpts, and the system prompts sent to the service's model, plus metadata (IP, timing, request IDs). Concretely:

1. **To the aggregator** (OpenRouter): your request body + usage metadata, governed by their privacy policy; OpenRouter states ZDR by default for many endpoints and offers per-request `provider.zdr: true`, `provider.data_collection: "deny"`, account-level training opt-out, and `eu.openrouter.ai` in-region routing (EU guarantee is Enterprise).
2. **To the upstream provider** (DeepInfra, Groq, Nebius, …): each has its own retention/training policy. Direct-provider mode means the user should read that provider's policy; OpenRouter's deny/ZDR flags remove the worst cases automatically.
3. **What stays local:** models, embeddings indexes, files, session state, usage logs (unless exported), and all local-mode traffic — nothing leaves the machine in local mode.
4. **Design rules for the platform:**
   - Per-service privacy tier: `local-only` (default), `cloud-no-retention` (ZDR + data_collection deny), `cloud-default`.
   - When enabling cloud, show the user *what data the service will send* (prompt text, attached media, system prompt) and to *whom*.
   - Never send secrets/credentials in prompts; keep the vault (Keycloak/Vault pattern) out of inference payloads.
   - Rate-limit and cap cloud spend per service (LiteLLM per-key budgets) so a runaway agent doesn't burn money silently.

---

## 10. Sources

- OpenRouter — one API for image/video/audio/embeddings/transcription: https://openrouter.ai/blog/insights/every-modality-one-api/
- OpenRouter — new audio APIs (TTS/STT): https://openrouter.ai/blog/announcements/announcing-audio-apis/
- OpenRouter — transcription guide: https://openrouter.ai/blog/tutorials/transcription-on-openrouter/
- OpenRouter — TTS docs: https://openrouter.ai/docs/guides/overview/multimodal/tts
- OpenRouter — API credit & rate limits: https://openrouter.ai/docs/api_reference/limits
- OpenRouter — free models router: https://openrouter.ai/openrouter/free
- OpenRouter — sovereign AI / ZDR / data_collection / EU routing: https://openrouter.ai/docs/guides/features/sovereign-ai · https://openrouter.ai/blog/insights/ai-data-residency/ · https://openrouter.ai/docs/guides/routing/provider-selection
- OpenRouter pricing (fees, free tier, plans): https://www.truefoundry.com/blog/openrouter-pricing · https://costgoat.com/pricing/openrouter
- OpenRouter model metadata (pricing, modalities, supported_parameters): https://openrouter.ai/openapi.json / `GET /api/v1/models`
- LiteLLM — home (MIT license, 140+ providers): https://www.litellm.ai/
- LiteLLM — proxy configs (fallbacks, context_window_fallbacks, load balancing, virtual keys): https://docs.litellm.ai/docs/proxy/configs
- LiteLLM routing local + cloud (config example, cost tracking): https://localaimaster.com/blog/ai-gateway-litellm
- Provider comparison (Fireworks blog, 8 providers incl. free tiers, Groq/Cerebras specifics): https://fireworks.ai/blog/best-llm-api-providers
- DeepInfra vs Fireworks pricing (38 shared models): https://pricepertoken.com/endpoints/compare/deepinfra-vs-fireworks
- Fireworks vs Together pricing 2026: https://www.morphllm.com/comparisons/fireworks-vs-together
- Groq vs Fireworks vs Together latency benchmark: https://hammansamuel.medium.com/comparing-api-providers-for-hosted-open-source-llms-3a5b2c9982fe
- DeepInfra — pricing & native API (embeddings, image, Whisper): https://deepinfra.com/pricing · https://docs.deepinfra.com/apis/deepinfra-native · https://docs.deepinfra.com/chat/overview
- DeepInfra — no free tier / 200 concurrent cap: https://www.morphllm.com/comparisons/together-vs-deepinfra
- Cerebras — 1M tokens/day free tier: https://www.cerebras.ai/blog/qwen3-235b-2507-instruct-now-available-on-cerebras · https://www.getaiperks.com/en/ai/cerebras-free-tier-guide · https://www.cerebras.ai/pricing
- Nebius AI Studio — vision/embeddings/LLMs, OpenAI-compatible, image pricing: https://nebius.com/blog/posts/studio-embeddings-vision-and-language-models · https://nebius.com/blog/posts/q1-2025-studio-updates
- Nebius — LiteLLM provider docs: https://docs.litellm.ai/docs/providers/nebius
- Nebius free tier (~$1 credit): https://pricepertoken.com/endpoints/nebius/free
- Hyperbolic — rate limits (60/min free): https://www.promptfoo.dev/docs/providers/hyperbolic/ · free-tier resources: https://github.com/cheahjs/free-llm-api-resources
- Together — pricing & free credits: https://www.together.ai/pricing · https://www.getaiperks.com/en/ai/together-ai-free-credits-2026
- Open WebUI — fallback model env/config: https://docs.openwebui.com/reference/env-configuration/ · https://docs.openwebui.com/features/workspace/models/
- LM Studio — Bionic / Secure Cloud / LM Link: https://lmstudio.ai/blog/introducing-lm-studio-bionic
- Jan — AGPL license + cloud providers: https://dev.to/worldlinetech/introducing-jan-38b9 · https://www.jan.ai/docs/desktop/manage-models
- Free-tier stack 2026 (DeepInfra 1M tok/day promo, Lepton $10): https://www.reddit.com/r/AI_Agents/comments/1t97zn9/
- Project references: `/opt/data/wordslab-agent/platform-studies/gpu/summary.md`, `…/text/openrouter-api.md`, `…/text/openai-api.md`, `…/implementation.md` (§1), `/opt/data/wordslab-platform/CONTEXT.md`
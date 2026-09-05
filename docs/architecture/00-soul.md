# The soul

Wordslab is the **ZX Spectrum, Amstrad CPC, BBC Micro, Thomson MO5 or Commodore 64 of the AI era** — a home-scale AI platform, 100% built from open-source components and models, the machine a generation learns on.

> **How to read this document:** this is the opening chapter of the Wordslab architecture. Read the chapters in order — soul first, then the big picture, then each layer and cross-cutting concern — in the reading order and conventions set out in `docs/architecture/README.md`. Where a chapter cites an ADR by id (e.g. ADR-0024), that ADR is the authoritative source of truth; the chapter organizes the view and never restates it.

## Who it is for

Our target audience is people who want to learn to use and to **understand** how AI works — non-technical at the start, but wanting to learn and understand in depth how it works, own their data, and **be in control** of what the AI does. No complex setup, everything familiar and guided end to end, but **no magic and no black box**: everything manually chosen, visible, and explained step by step.

Two audiences are deliberately not ours. People who just want to use AI and don't want to invest the time and effort to understand and stay in control can use ChatGPT — we are not competing with that. And highly technical people who already understand how the internals of vLLM work, to optimize their LLM deployments on large-scale clusters, are not our target audience either. Wordslab is deployed in a trusted environment at a very small scale — never a "serve millions" system.

## The home-computer analogy

AI is a new form of computing, and we are trying to reproduce what happened at the beginning of the home computer market at the start of the eighties. First everybody paid to game in arcades, because the machines were too expensive to run at home. Then consoles appeared, to be able to game at home for people who didn't want to understand. But millions learned what a computer was by interacting with the first home computers you could program. Later the field matured enough that we didn't need to know how to code — but in the first ten years of personal computing, people needed to understand, before machines and operating systems became too complex.

We are trying to build the **ZX Spectrum, Amstrad CPC, BBC Micro, Thomson MO5 or Commodore 64 of the AI era**, so that millions can learn the AI basics at home, in schools, or in small enterprises — on machines they can afford, taking them where they are in their technical understanding of the matter. The ambition is to be the **machine a generation learns on** (ADR-0024 names this educational goal as the platform's stated main goal).

## The three commitments

Everything in this architecture traces back to that soul. Three commitments run through every service, every capability, and every principle:

1. **Openness** — 100% open source, and honestly visible.
2. **Simplicity** — the main feature; small scale, self-hosted, understandable.
3. **Control** — the user owns their data, chooses their implementations, and sees what the AI does.

## No magic, no black box

The phrase that recurs in every design decision is **"no magic, no black box"**: nothing is silently routed, auto-decided, or hidden. Where most platforms would put a heuristic or a scheduler, Wordslab puts a visible choice and an explanation. This one sentence explains most of the architecture — when you wonder *"why isn't this automatic?"*, the answer is almost always the soul.

## Project overview

This repository contains a production-ready Telegram AI Bot for generating images with paid access via Russian payment providers and compliance with 54‑FZ requirements. The bot targets Python 3.11+, is containerized with Docker, and is optimized to run inference efficiently on modern NVIDIA GPUs (e.g. RTX 40xx / RTX 5080–class hardware).[file:1]

The project includes: 
- Telegram bot logic (handlers, commands, user flows). 
- AI image generation pipeline. 
- Payment integration (e.g. YooKassa / bank acquiring) with receipt / fiscal logic aligned with Russian regulations.[file:1]

## Dev environment tips

- Use Python 3.11 or newer and create a virtual environment before installing dependencies.
- Prefer installing all dependencies from the project’s pinned list (requirements / pyproject) instead of ad‑hoc `pip install` to avoid version drift.
- Use Docker for a production-like environment: the image should contain GPU drivers / CUDA support where applicable and be as slim as possible (multi-stage builds are preferred).
- Keep all secrets (Telegram bot token, payment provider keys, webhook secrets) in `.env` files or secret stores; never hardcode them into source files or commit them.
- When working on GPU-related code, check available VRAM and use batching / mixed precision where possible to keep inference fast and memory usage stable.

## Build and run

- Local run (dev mode): 
  - Install dependencies with the project’s documented package manager (e.g. `pip install -r requirements.txt` or equivalent).
  - Run the bot’s main entrypoint (e.g. `python -m <main_module>` or the specified CLI script).
- Docker:
  - Build the image using the provided Dockerfile (e.g. `docker build -t telegram-ai-bot .`).
  - Run the container with required environment variables mounted from `.env` and, if using GPU, make sure to enable GPU access (e.g. `--gpus all` where supported).

Agents MUST:
- Confirm the primary entrypoint files and commands from README / Docker configuration before suggesting changes.
- Keep Docker commands in sync with any changes to dependencies or app structure.

## Testing instructions

- Before proposing refactors or large changes, search for existing tests (e.g. `tests/` or `*_test.py`) and keep their structure and framework consistent.
- For new features or bugfixes, add or update tests so that:
  - Payment flows are covered (success, failure, cancellation, retries).
  - AI generation is at least smoke-tested (valid response, correct image format, no crashes on GPU/CPU).
- Prefer `pytest` or the existing framework; do not introduce a second testing framework without explicit instruction.
- After modifying critical paths (payments, webhooks, auth, main bot loop), agents should:
  - Propose test commands (e.g. `pytest -q` or specific test files).
  - Include steps to run tests inside Docker if relevant.

## Code style guidelines

- Follow the existing style visible in the repository: naming, imports, and project structure should be preserved unless explicitly asked to refactor.
- Use type hints for new or changed Python code where it improves clarity and safety, especially in public functions, integrations, and core business logic.
- Keep modules focused:
  - Telegram handlers in their own layer / module.
  - Business logic separate from I/O (Telegram, payments, filesystem, network).
  - Payment integration isolated behind clear interfaces or service classes.
- Minimize magic constants: configuration values (API URLs, timeouts, limits, tariff parameters) should go to config modules or environment-based settings.

## Security considerations

- Never expose or log full secrets, card data, or other sensitive details (tokens, API keys, personal data).
- For payment flows:
  - Always validate incoming webhook data (signatures, IP / origin checks if supported by the provider).
  - Treat all external callbacks as untrusted input and validate payloads before use.
- Do not weaken existing input validation or error handling in payment and AI endpoints without a clear reason.
- When adding new dependencies:
  - Prefer well-maintained, widely used libraries.
  - Avoid introducing libraries that duplicate existing functionality unless explicitly requested.

## Payment and 54‑FZ specifics

- Changes to payment logic MUST:
  - Preserve the current business flow: initiation → payment provider → callback / webhook → status update → receipt / user notification.
  - Respect 54‑FZ related logic already present in the project (receipt generation, status tracking, correct reporting pipeline).
- If a change requires altering:
  - Payment status enums / constants.
  - Webhook handlers.
  - Fiscal / receipt logic.
  
  The agent should:
  - Explicitly call out the impact of the change.
  - Propose tests or test scenarios covering successful, failed, and edge-case payments.
- If the legal implications are unclear, agents should state that they describe technical implementation only and cannot guarantee legal compliance.

## GPU and performance notes

- Aim to keep image generation efficient:
  - Avoid unnecessary model reloads on each request.
  - Use batching or queueing if high concurrency is expected.
  - Consider mixed precision or other optimizations supported by the chosen framework (e.g. PyTorch / ONNX / TensorRT).
- When touching AI code, agents should:
  - Describe the performance impact of changes when possible.
  - Avoid drastically increasing VRAM usage or latency without a strong reason.

## Agent behavior

Agents working on this repository SHOULD:

- Read README, configuration files, and the bot’s main modules before making non-trivial changes.
- Start responses with:
  - A short **analysis** of the current situation.
  - A clear **plan** in numbered steps.
- Propose changes as:
  - Small, focused patches with clear filenames and code blocks per file.
  - Or explicit diffs grouped by file, avoiding unrelated edits in the same change.
- When the requested change is large:
  - Split it into smaller milestones (e.g. “first adjust handlers”, “then update payment layer”, “finally AI optimizations”).
  - Indicate what should be tested manually after each milestone.

Agents MUST NOT:

- Remove or radically rewrite working payment or fiscal logic unless explicitly requested.
- Change public interfaces (e.g. core bot commands, key data structures, webhook payload formats) without calling this out and explaining the impact.
- Add non-trivial new external services or infrastructure (databases, queues, third-party APIs) on their own initiative.

## How to extend AGENTS.md

- When new subsystems are added (e.g. separate admin panel, analytics service, or new payment provider), add a short section:
  - What it does.
  - How to run it.
  - Any critical invariants or compliance rules.
- Keep this file concise but precise: it should tell agents what is important, how to run and test the project, and what they must not break.


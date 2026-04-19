# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

- Install deps: `uv sync` (preferred) or `pip install -r requirements.txt`
- Run the interactive chatbot: `./main.py` (shebang is `uv run --script`)
- Check one or more domains directly: `./check_domain.py example.com` or pipe a list via stdin
- There is no test suite, linter, or build step configured.

## External dependencies / secrets

- DeepSeek API key must exist at `~/.mingdaoai/deepseek.key` (see `utils.load_api_key`). The OpenAI SDK is pointed at `https://api.deepseek.com` via `OpenAIHelper`.
- AWS credentials (env vars or `aws configure`) are optional but enable the Route 53 Domains path. `route53-policy.json` has the minimal IAM policy (`route53domains:CheckDomainAvailability`, `ListPrices`, region `us-east-1`).

## Architecture

The repo is a small CLI with two entrypoints that share the same checking core:

- `main.py` — interactive chatbot loop. It (1) asks the user for an idea, (2) calls DeepSeek via `OpenAIHelper.generate_domain_names` for ~20 `.com` suggestions, (3) checks each through `domain_checker.check_domain_availability`, and (4) feeds previously-seen domains back into the next prompt to avoid duplicates. It keeps regenerating until at least one new available domain is found per iteration.
- `check_domain.py` — non-interactive availability checker (CLI args or stdin). Reuses the same `domain_checker` + logging setup.

### Domain availability pipeline (`domain_checker.py`)

`check_domain_availability` is the single public entry and implements a deliberate fall-through order:

1. **DNS lookup** (`check_dns_records`) against 8.8.8.8/1.1.1.1/9.9.9.9, checking A/AAAA/MX/NS/CNAME/TXT/SOA. Any positive record => `taken`; NXDOMAIN or no records anywhere => treat as `available` and continue verifying.
2. **AWS Route 53 Domains** (`check_aws_route53`) — authoritative for `.com`. Mapped statuses: `AVAILABLE*` → available; `UNAVAILABLE*`/`RESERVED` → taken; `PENDING` retries. Has a module-level rate limit of 1 call/sec (`_rate_limit_aws_calls`) plus exponential backoff on `ThrottlingException`/`RequestLimitExceeded`.
3. **WHOIS fallback** (`check_whois_fallback`) — only if AWS fails/is unconfigured. Presence of `domain_name` in the whois record means taken.

Status is always returned as `(is_available, status)` where `status ∈ {'available','taken','error'}`. Both CLIs wrap this in `check_domain_with_backoff` (retries on `error` only, not on definitive `taken`/`available`).

### Caching and history (main.py)

All persistent state lives under `./.cache/`:

- `query_history.json` — every idea the user typed; re-loaded into `readline` so arrow-keys recall past queries.
- `.domain_finder_history` — raw readline history file.
- `domains_<slugified-query>.json` — per-query accumulator with the full list of known `available_domains`/`unavailable_domains` and a `searches[]` log. `save_domains_to_cache` deduplicates and, on conflict, trusts the more recent check (removes from unavailable).
- `logs/domain_check_<timestamp>.log` — written by `logging_config.setup_logging` (console at INFO, file at DEBUG, immediate flush + `fsync` via custom handlers).

### Prompting behavior

`get_max_domain_length` in `main.py` computes a per-query length cap (90th percentile of known domains, clamped to `[12, 30]`, but never shorter than the longest already-available domain). This cap is embedded in the DeepSeek prompt as a hard limit and also used to post-filter suggestions in `check_domains_batch`. The prompt also imposes content constraints (phonetically clear, memorable when heard, singular, pinyin-friendly, no Japanese words) — if you change the prompt, preserve these unless the user asks otherwise.

### Things that are easy to miss

- `OpenAIHelper.generate_domain_names` has an `assert "domain" in user_input` — callers must include the word "domain" in the prompt or it will raise.
- Both entrypoints have their own `check_domain_with_backoff` copy; they are intentionally duplicated and differ only slightly in logging calls.
- `main.py` and `check_domain.py` have `uv run --script` shebangs, so executing them directly requires `uv` on PATH.

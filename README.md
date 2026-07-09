# Hermes News Briefings

Repository for daily morning news briefings. The flow is:
ChatGPT publishes a new briefing into this repository, Hermes Agent reads `latest/briefing.md`, and then Hermes sends it to Telegram.

## Layout

- `latest/briefing.md` - human-readable latest briefing
- `latest/briefing.json` - machine-readable latest briefing
- `reports/YYYY/MM/YYYY-MM-DD.md` - daily archive
- `archive/topics-log.jsonl` - used-topic log to avoid repeats
- `config/profile.yaml` - profile and filtering rules
- `config/hermes.example.yaml` - Hermes source and delivery example
- `schemas/briefing.schema.json` - JSON schema for `briefing.json`
- `scripts/hermes_fetch_latest.py` - fetch and send the latest briefing
- `docs/OPERATING_MODEL.md` - operating schedule and responsibilities

## Publishing model

ChatGPT writes a new briefing every morning and updates:

1. `latest/briefing.md`
2. `latest/briefing.json`
3. `reports/YYYY/MM/YYYY-MM-DD.md`
4. `archive/topics-log.jsonl`

Hermes reads only `latest/briefing.md` for delivery, while `latest/briefing.json` supports validation and deduplication.

## Telegram delivery

The delivery script expects:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Optional:

- `BRIEFING_RAW_URL` - raw GitHub URL of `latest/briefing.md`
- `BRIEFING_CONFIG` - path to Hermes YAML config

## Notes

- No secrets are stored in this repository.
- The script skips duplicate delivery when `send_only_if_file_changed` is enabled.
- The repo is ready to be pushed to GitHub once authentication is available.

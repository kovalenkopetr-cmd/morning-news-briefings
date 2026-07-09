# Operating Model

## Daily flow

- 05:05 - ChatGPT prepares the briefing and writes:
  - `latest/briefing.md`
  - `latest/briefing.json`
  - `reports/YYYY/MM/YYYY-MM-DD.md`
  - `archive/topics-log.jsonl`
- 05:10 - Hermes Agent reads `latest/briefing.md` from GitHub raw
- 05:11 - Hermes Agent sends the briefing to Telegram

## Roles

- ChatGPT: produce the daily briefing and publish the repository files
- Hermes: fetch the latest file and deliver it to Telegram
- GitHub: durable storage and version history

## Delivery rules

- Send only when the file is non-empty
- Skip duplicates when `send_only_if_file_changed` is enabled
- Split long Telegram messages when needed
- Keep secrets outside the repository

## Telegram environment

The delivery script requires:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Optional runtime variables:

- `BRIEFING_RAW_URL`
- `BRIEFING_CONFIG`

## Topic log

`archive/topics-log.jsonl` stores one JSON object per line so repeated topics can be suppressed unless the story has a new material development.

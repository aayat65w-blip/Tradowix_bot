# MONARCH Telegram Bot — Railway

Upload every file in this bundle to the **root** of one GitHub repository:

```text
monarch_tgbot.py  quotex.py  tg_engine.py  tg_ui.py
requirements.txt  nixpacks.toml  Procfile  .python-version
```

## Railway mobile setup

1. Railway → New Project → Deploy from GitHub repo.
2. Service → Variables → add `BOT_TOKEN` and `OWNER_ID` without quotes.
3. Deploy, then send `/start` to the bot in Telegram.

It is a worker, so no public domain or `PORT` variable is needed. Start command is already `python -u monarch_tgbot.py`.

## Security

Never put a real token in README, `.env.example`, GitHub, or code. If exposed, use BotFather `/revoke`, then save only the new token in Railway Variables.

## Errors

- `can't open file monarch_tgbot.py`: files are not in repository root.
- `BOT_TOKEN is missing`: add Railway Variables and redeploy.
- `ModuleNotFoundError`: verify root `requirements.txt` and install logs.
- Telegram conflict: stop any other deployment/process polling the same bot.
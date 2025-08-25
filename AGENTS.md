# AGENTS Instructions

This repository powers a Discord bot built around modular extensions and utilities. This file summarizes the layout and guidelines for AI contributors.

## Project Structure

- `main.py` – Entry point; loads configuration and bootstraps the bot.
- `bot.py` – Sets up the Discord bot and loads extensions.
- `dependencies/` – Helper modules (logging, encryption, APIs, etc.).
- `extensions/` – Active bot features implemented as `commands.Cog` modules with an `async def setup`.
- `inactive_extensions/` – Archived or experimental extensions. These are not loaded; modify only if reactivating a feature.
- `logger.py` – Centralized logging utilities.
- `requirements.txt` – Python dependencies.
- `docker-compose-demo.yml` – Example container configuration.

## Interaction Guidelines for AIs

- Keep code modular: new features belong in `extensions/`; shared helpers go in `dependencies/`.
- Follow PEP 8 style, use type hints and docstrings similar to existing files.
- Each module should obtain a logger via `LoggerManager` and write to `logs/<name>.log`.
- Update `requirements.txt` when adding external libraries.
- Avoid altering files in `inactive_extensions/` unless bringing a feature back.

## Programmatic Checks

No dedicated test suite exists. After modifying Python files, ensure they compile:

```bash
python -m py_compile <file1> <file2> ...
```

For a full repository check:

```bash
python -m py_compile $(git ls-files '*.py')
```

Run the relevant command and make a best effort to confirm success before committing changes.
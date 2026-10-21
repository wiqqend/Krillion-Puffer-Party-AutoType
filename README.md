# Puffer Party Bot

This script plays Krillion Puffer Party for you. It reads the category, finds it in the answer archive, and types a rare answer on your turn.

## Setup

1. Install Python 3.9 or newer.
2. Install the browser tools:

```
pip install playwright
playwright install chromium
```

3. Put `puffer_bot.py` in a folder of its own.

## First run

Download the answer archive. This takes a few minutes and only needs to happen once.

```
python puffer_bot.py --build
```

This creates `answers.json` in the same folder.

## Check that it works

```
python puffer_bot.py --inspect
```

A browser window opens. Log in and join a lobby, then press Enter in the terminal. The script prints the category it sees, whether it found the answer box, and whether it detects your turn. All three should say yes or show the right text.

## Play

Test run first. It prints its picks and types nothing.

```
python puffer_bot.py --dry
```

Real run:

```
python puffer_bot.py
```

Log in, join a lobby, and press Enter in the terminal. The bot waits for your turn and answers. Press Ctrl+C to stop.

## Options

| Command | What it does |
| --- | --- |
| `--build` | Downloads the answer archive |
| `--inspect` | Shows what the bot sees on the page |
| `--dry` | Prints picks without typing |
| `--strict` | Uses only Deep Cut and One in a Krillion answers |
| `--paste file.txt` | Adds an archive page you copied into a text file |

## How it picks answers

- It tries One in a Krillion answers first, then Deep Cut.
- It uses Rare answers only when the better ones run out. Use `--strict` to turn this off.
- It never repeats an answer in the same category.
- It skips answers that already appear on screen.
- If the game rejects an answer, it tries another on the next turn.

## Troubleshooting

**The bot never answers.** Run `--inspect`. If it does not detect your turn, open `puffer_bot.py` and change `TURN_RE` near the top to match the text the game shows on your turn.

**It says no archive match.** The category is not in the archive. Copy a recent archive day page into a text file and run `--paste file.txt`.

**`--build` finds nothing.** Copy an archive day page into a text file and use `--paste` instead.

**It cannot find the answer box.** Change `INPUT_PLACEHOLDER` near the top of the script.

## Notes

- The bot cannot guarantee a Deep Cut. Another player may take the answer first.
- Automated play may break the game's rules. Use it at your own risk.
- Your login is saved in a `profile` folder next to the script. Do not share it.

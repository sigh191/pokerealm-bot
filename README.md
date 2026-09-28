# PokeRealm

A Discord bot RPG where players catch, train, and evolve Pokémon. Built as a CM3070 Final Project (BSc Computer Science, University of London), based on the CM3020 "Orchestrating AI Models to Achieve a Goal" template.

Three separate pre-trained AI models are orchestrated together, each working on a different data domain, to bring a small piece of the game to life:

| Model | Domain | What it does |
|---|---|---|
| Llama 3.2 (3B), via a local Ollama server | Text | Generates the scene/objective/dialogue for `/explore` quests |
| CLIP (`openai/clip-vit-base-patch32`) | Image | Classifies a Pokémon's sprite to get a "vibe" (e.g. fiery, spooky) that feeds into the quest prompt |
| CLAP (`laion/clap-htsat-unfused`) | Audio | Classifies a Pokémon's cry to get a "sound" (e.g. deep and powerful) that also feeds into the quest prompt |

Everything the AI models produce is narrative/flavour only. Every outcome that actually affects gameplay - catch success, catch rarity, quest rewards, evolution, the rare legendary bonus - is decided by plain, deterministic Python (see `pokemon/`), not by a model. This split is a deliberate design decision, not a limitation - it keeps the game fair and testable while still genuinely using AI for the parts that benefit from it.

## Features

- `;catch` / `/catch` - look for a wild Pokémon to catch, with rarity-weighted odds
- `;explore` / `/explore` - type any location and get an AI-generated quest there, with a small chance of a legendary (Ho-Oh or Lugia) joining you at the end
- `;shop` / `/shop`, `;coins` / `/coins` - spend coins earned from catching and questing on upgrades
- `;team` / `/team`, `;box` / `/box`, `;move` / `/move` - manage your party and storage
- `;evolve` / `/evolve` - evolve your lead Pokémon once it's high enough level
- `;inventory` / `/inventory` - check the items you own
- `;promo` / `/promo` - claim the current free promotional Pokémon
- `;ping` / `/ping` - check the bot is online

Every command works both as a slash command (`/catch`) and as a classic prefix command (`;catch`) from a single definition, using discord.py's hybrid commands.

## Project structure

```
bot.py              - entry point: loads config, registers commands, starts the bot
commands/           - one file per Discord command
pokemon/            - deterministic game logic (encounters, growth, evolution, economy - no AI here)
ai/                 - the three AI model integrations (Llama, CLIP, CLAP) and quest generation
database/           - SQLite persistence layer (players, migrations)
evaluation/         - scripts/metrics used to evaluate the project (e.g. lexical diversity of generated quests)
tests/              - pytest unit test suite
```

## Setup

**Requirements:** Python 3.10+, and [Ollama](https://ollama.com) installed and running locally (used for the text-generation model).

1. Clone the repo and install dependencies:
   ```
   pip install -r requirements.txt
   ```
   For running the test suite as well:
   ```
   pip install -r requirements-dev.txt
   ```

2. Pull the Llama model Ollama will use:
   ```
   ollama pull llama3.2:3b
   ```
   Make sure `ollama serve` is running (Ollama usually starts this automatically) before starting the bot - it's expected at `http://localhost:11434`.

3. Create a Discord application and bot at the [Discord Developer Portal](https://discord.com/developers/applications), and under **Bot**, turn on **Message Content Intent** (required for the `;`-prefix commands to work).

4. Create a `.env` file in the project root:
   ```
   DISCORD_TOKEN=your-bot-token-here
   TEST_GUILD_ID=your-test-server-id-here
   ```
   `TEST_GUILD_ID` is optional - it makes slash commands sync instantly to one server while developing, instead of taking up to an hour to sync globally. Leave it out for a normal/production run.

5. Run the bot:
   ```
   python bot.py
   ```
   The SQLite database (`data/pokerealm.db`) is created automatically on first run.

## Running the tests

```
pytest
```

110 unit tests across the `tests/` folder, covering the deterministic game logic (catch odds, levelling, evolution, economy, database migrations) and the non-AI parts of the AI orchestration (JSON-parsing fallbacks, etc). Tests that would need a real running Ollama server, network access, or the CLIP/CLAP models downloaded are mocked out, so the whole suite runs in under a second with nothing extra needed.

## Academic context

This is a submission for the CM3070 Final Project module, built on the CM3020 template "Orchestrating AI Models to Achieve a Goal." The full project report (design rationale, evaluation, and discussion of results) is submitted separately and isn't included in this repository.

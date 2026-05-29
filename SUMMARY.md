# Project Structure

## Directory Layout
- **`src/mu/`** – Python package (the `mu` command)
- **`dojo/`** – Experimental runs and agent outputs
- **`docs/`** – Documentation
- **`skills/`** – Skill prompts injected into the planner

## Key Components

### 1. `mu` command
- Installed via `pip install -e .` (or `make install`)
- Entry point: `mu.__main__:main`

### 2. `dojo/` Directory
- Contains versioned subdirectories for agent runs:
  - `claude-qwen3-8b-...` (experiment versions)
  - Each may contain:
    - `logs/` – Agent operation logs
    - `generated/` – Code/output produced by agents

### 3. `run.sh` Script
- Located in `dojo/run.sh`
- Orchestrates agent runs and outputs to dojo subdirectories

## Available Commands
- `mu` (primary CLI)
- `./dojo/run.sh` (agent execution script)
- Makefile targets (see `Makefile` for details)

## Notes
- Agent runs create versioned directories in `dojo`
- Logs and generated code are stored in experiment-specific subdirectories

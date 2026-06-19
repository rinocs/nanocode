# nanocode

Minimal coding-agent harness. Single Python file, zero dependencies, ~300 lines.

Built for speed, hackability, and minimal overhead.

## Features

- **Agentic Loop**: Full tool-use cycle with Claude (Anthropic/OpenRouter).
- **Harness Abstraction**: Clean separation of Session, Memory, and Tools.
- **Minimal Memory**: JSON-based persistent history and scratchpad.
- **Sub-Agents**: Optional Planner and Reviewer roles for complex tasks.
- **Standard Tools**: `read`, `write`, `edit`, `glob`, `grep`, `bash`.

## Usage

```bash
export ANTHROPIC_API_KEY="your-key"
python nanocode.py
```

### Configuration (Environment Variables)

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL` | `claude-3-5-sonnet` | Model ID to use |
| `MEMORY` | `1` | Enable/disable persistent memory |
| `PLANNER` | `0` | Enable/disable sub-agent planning |
| `REVIEWER` | `0` | Enable/disable sub-agent reviewing |
| `VERBOSE` | `0` | Enable debug/verbose output |

### Commands

- `/c` - Clear conversation and memory
- `/q` or `exit` - Quit

## Memory

Memory is stored in `.nanocode_memory.json`. It includes:
- **History**: Last 20 messages for context.
- **Scratchpad**: Persistent storage for long-term facts (edit manually if needed).

## Sub-Agents

- **Planner**: Before starting, a planner agent creates a step-by-step plan.
- **Reviewer**: After completion, a reviewer agent verifies the work and suggests fixes.

## Development

Run tests with:
```bash
python3 test_nanocode.py
```

## License

MIT

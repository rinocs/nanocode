# Agent Guidelines for nanocode

This repository is designed to be extremely minimal. When modifying or extending `nanocode`, follow these rules:

### 1. Minimalist Core
- Keep the main logic in `nanocode.py`.
- Prefer the Python Standard Library over external dependencies.
- Avoid heavy abstractions (no DI frameworks, no complex inheritance).

### 2. File Conventions
- `nanocode.py`: The core engine.
- `test_nanocode.py`: Unit tests for the engine.
- `.nanocode_memory.json`: Local state (do not commit).

### 3. Architecture Expectations
- **Harness**: The `Session` class handles API interactions and message state.
- **Tools**: Keep tool implementations simple and side-effect predictable.
- **Memory**: Memory should be bounded and transparent. Use JSON for readability.

### 4. Testing
- Always update `test_nanocode.py` when changing core logic.
- Ensure tests remain lightweight and run in under 1 second.

### 5. Do Not Over-Engineer
- If a feature can be implemented in 10 lines of clear code, do not use 50 lines of "clean" architecture.
- Prefer explicit over implicit.
- Backward compatibility with the basic CLI flow is mandatory.

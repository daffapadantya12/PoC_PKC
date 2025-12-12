<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.9%2B-blue" alt="Python 3.9+" /></a>
  <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="MIT License" /></a>
  <a href="https://github.com/astral-sh/ruff"><img src="https://img.shields.io/badge/code%20style-ruff-000000.svg" alt="ruff" /></a>
  <a href="https://github.com/xlp0/MCard_TDD/actions/workflows/ci.yml"><img src="https://github.com/xlp0/MCard_TDD/actions/workflows/ci.yml/badge.svg" alt="Build Status" /></a>
</p>

# MCard

MCard is a local-first, content-addressable storage platform with cryptographic integrity, temporal ordering, and a Polynomial Type Runtime (PTR) that orchestrates polyglot execution. It gives teams a verifiable data backbone without sacrificing developer ergonomics or observability.

---

## Highlights
- 🔐 **Hash-verifiable storage**: SHA-256 hashing, handle registry with history, immutable audit trail output.
- ♻️ **Deterministic execution**: PTR mediates **8 polyglot runtimes** (Python, JavaScript, Rust, C, WASM, Lean, R, Julia).
- 📊 **Enterprise ready**: Structured logging, CI/CD pipeline, security auditing, 99%+ automated test coverage.
- 🧠 **AI-native extensions**: GraphRAG engine, optional LLM runtime, and optimized multimodal vision (`moondream`).
- 🧰 **Developer friendly**: Rich Python API, TypeScript SDK, BMAD-driven TDD workflow, numerous examples.
- 📐 **Algorithm Benchmarks**: Sine comparison (Taylor vs Chebyshev) across Python, C, and Rust.
- ⚡ **High Performance**: Optimized test suite (~37s) with runtime caching and session-scoped fixtures.

For the long-form narrative and chapter roadmap, see **[docs/Narrative_Roadmap.md](docs/Narrative_Roadmap.md)**. Architectural philosophy is captured in **[docs/architecture/Monadic_Duality.md](docs/architecture/Monadic_Duality.md)**.

---

## Quick Start (Python)
```bash
git clone https://github.com/xlp0/MCard_TDD.git
cd MCard_TDD
./activate_venv.sh          # installs uv & dependencies
uv run pytest -q -m "not slow"  # run the fast Python test suite
uv run python -m mcard.ptr.cli run chapters/chapter_01_arithmetic/addition.yaml
```

Create and retrieve a card:
```python
from mcard import MCard, default_collection

card = MCard("Hello MCard")
hash_value = default_collection.add(card)
retrieved = default_collection.get(hash_value)
print(retrieved.get_content(as_text=True))
```

### Quick Start (JavaScript / WASM)
See **[mcard-js/README.md](mcard-js/README.md)** for build, testing, and npm publishing instructions for the TypeScript implementation.

---

## Polyglot Runtime Matrix
| Runtime    | Status | Notes |
| ---------- | ------ | ----- |
| Python     | ✅ | Reference implementation, CLM runner |
| JavaScript | ✅ | Node + browser (WASM) + Full RAG Support |
| Rust       | ✅ | High-performance adapter & WASM target |
| C          | ✅ | Low-level runtime integration |
| WASM       | ✅ | Edge and sandbox execution |
| Lean       | ⚙️ | Formal verification pipeline (experimental) |
| R          | ✅ | Statistical computing runtime |
| Julia      | ✅ | High-performance scientific computing |

---

## Project Structure (abridged)
```
MCard_TDD/
├── mcard/            # Python package (engines, models, PTR)
├── mcard-js/         # TypeScript implementation & npm package
├── chapters/         # CLM specifications (polyglot demos)
├── docs/             # Architecture, PRD, guides, reports
├── scripts/          # Automation & demo scripts
├── tests/            # >450 automated tests
└── requirements.txt / pyproject.toml
```

---

## Documentation
- Product requirements: [docs/prd.md](docs/prd.md)
- Architecture overview: [docs/architecture.md](docs/architecture.md)
- Monad–Polynomial philosophy: [docs/architecture/Monadic_Duality.md](docs/architecture/Monadic_Duality.md)
- Narrative roadmap & chapters: [docs/Narrative_Roadmap.md](docs/Narrative_Roadmap.md)
- Logging system: [docs/LOGGING_GUIDE.md](docs/LOGGING_GUIDE.md)
- PTR & CLM reference: [docs/CLM_Language_Specification.md](docs/CLM_Language_Specification.md), [docs/PCard%20Architecture.md](docs/PCard%20Architecture.md)
- Reports & execution summaries: [docs/reports/](docs/reports/)

---

## Recent Updates (December 2025)

### Version 0.1.30 / 2.1.10 — December 10, 2025

#### Handle Validation Improvements
- **Relaxed Handle Rules**: Handles now support periods (`.`), spaces (` `), and forward slashes (`/`) to accommodate file paths and filenames.
- **Extended Length**: Maximum handle length increased from 63 to 255 characters for better file path compatibility.
- **Cross-Runtime Parity**: Synchronized validation logic between Python (`mcard/model/handle.py`) and JavaScript (`mcard-js/src/model/Handle.ts`).
- **Updated Tests**: All handle validation tests updated across both runtimes to reflect new rules.

#### Loader Return Type Standardization
- **Structured Response**: `load_file_to_collection` now returns `{metrics, results}` instead of a plain array.
- **Metrics Object**: Includes `filesCount`, `directoriesCount`, and `directoryLevels` for better observability.
- **Test Updates**: Updated all loader tests to use `response.metrics.filesCount` and `response.results` array.

#### Python Runtime Wrapper Enhancements
- **Smart Function Invocation**: Python wrapper now tries calling with `context` dict first, then `target`, then no args.
- **Error Discrimination**: Added `_is_arg_error()` helper to distinguish TypeError about function arguments from other TypeErrors (e.g., sorting errors).
- **Proper Scope Resolution**: Fixed entry point lookup using `dir()` and `globals()` instead of `locals()`.
- **Builtin Loader Support**: JavaScript PTR now recognizes `builtin: loader` for Python CLMs.

#### Bug Fixes
- **Reflection Logic Sorting**: Fixed `generate_inventory()` and `weave_narrative()` to handle mixed ID types (int, float, string) during sorting.
- **CLM Loader Detection**: Added support for `builtin: load_files` in addition to existing loader detection methods.

### Session: December 10, 2025 — CLM Execution Refinements

#### CLM Runner & Test Infrastructure
- **Unified Python CLI (`scripts/run_clms.py`)**: Single script to run all CLMs, by directory, or individual files with optional `--context` JSON injection.
- **Fast Test Mode**: Added `@pytest.mark.slow` to Lean-dependent tests; run fast tests with `uv run pytest -m "not slow"` (~20s vs 2+ minutes).
- **Params Interpolation**: Fixed `balanced.test_cases` to properly preserve `when.params` for `${params.xxx}` variable substitution in config.
- **Recursive Interpolation**: Added `_interpolate_recursive()` to NetworkRuntime for nested batch operation configs.

#### Runtime Fixes
- **Unified Execution**: Python and JavaScript runtimes now execute the same set of CLMs with parity in path resolution, context passing, and builtin handling.
- **Python Context Passing**: Fixed `_prepare_argument` to pass context with `operation`/`params` keys to entry point functions—resolves complex arithmetic test failures.
- **JavaScript Path Resolution**: Fixed relative path execution issues in `CLMRunner`; CLMs now correctly resolve recursive calls and legacy formats regardless of execution context.
- **Collection Loader**: Enabled `collection_loader` runtime in JavaScript (`CollectionLoaderRuntime`) and verified with integration tests.
- **Builtin Test Cases**: Builtins (network runtime) now correctly execute `balanced.test_cases` instead of bypassing them.
- **Orchestrator Input Override**: CLMs called via orchestrator with explicit inputs (e.g., `signaling_url`) now skip default test cases.

#### Chapter-Specific Fixes
- **chapter_01_arithmetic**: All 27 CLMs passing across Python and JS runtimes.
- **chapter_07_network**: Fixed `http_fetch.yaml` to use `runtime: network`, enabling cross-platform HTTP execution.
- **chapter_08_P2P**: 13 CLMs passing, 3 skipped (Node.js-only marked as VCard).
  - WebRTC CLMs use `mock://p2p` for standalone testing.
  - Orchestrator overrides `signaling_url` for real connections.
  - Converted `persistence_simulation` and `long_session_simulation` from JavaScript to Python for better stability.

### Previous Updates

#### CLM Test Infrastructure Improvements
- **Execution Timing**: Added timing logs to `run-all-clms.ts` to identify slow CLMs.
- **Floating-Point Tolerance**: Numeric comparisons now use configurable tolerance (1e-6) for floating-point precision.
- **Input Context Handling**: Introduced `__input_content__` key to preserve original `given` values when merging `when` blocks.

#### Runtime Fixes (Prior Sessions)
- **JavaScript Runtime**: Changed `runtime: node` to `runtime: javascript` across CLMs; updated code to use `target` variable.
- **Python Input Parsing**: All Python implementations now handle `bytes`, `str`, and `dict` inputs with robust parsing.
- **Lambda Calculus**: Fixed parser to correctly handle parenthesized applications like `(\\x.x) y`.
- **Orchestrator**: Fixed `run_clm_background` to strip file extensions for proper filter matching.

#### Chapter-Specific Fixes (Prior Sessions)
- **chapter_03_llm**: Replaced LLM-dependent logic with mock implementations for test stability.
- **chapter_05_reflection**: Fixed meta-interpreter and module syntax CLMs.
- **chapter_06_lambda**: Fixed beta reduction and Church numerals parsers.

---

## Testing

> **Note:** All commands below should be run from the project root (`MCard_TDD/`).

### Unit Tests

```bash
# Python
uv run pytest -q                 # Run all tests
uv run pytest -q -m "not slow"   # Fast tests only
uv run pytest -m "not network"   # Skip LLM/Ollama tests

# JavaScript
npm --prefix mcard-js test
```

### CLM Verification

Both Python and JavaScript CLM runners support three modes: **all**, **directory**, and **single file**.

#### Python

```bash
# Run all CLMs
uv run python scripts/run_clms.py

# Run by directory
uv run python scripts/run_clms.py chapters/chapter_01_arithmetic
uv run python scripts/run_clms.py chapters/chapter_08_P2P

# Run single file
uv run python scripts/run_clms.py chapters/chapter_01_arithmetic/addition.yaml

# Run with custom context
uv run python scripts/run_clms.py chapters/chapter_08_P2P/generic_session.yaml \
    --context '{"sessionId": "my-session"}'
```

#### JavaScript

```bash
# Run all CLMs
npm --prefix mcard-js run clm:all

# Run by directory/filter
npm --prefix mcard-js run clm:all -- chapter_01_arithmetic
npm --prefix mcard-js run clm:all -- chapters/chapter_08_P2P

# Run single file
npm --prefix mcard-js run demo:clm -- chapters/chapter_01_arithmetic/addition_js.yaml
```

### Chapter Directories

| Directory | Description |
|-----------|-------------|
| `chapter_00_prologue` | Lambda calculus and Church encoding |
| `chapter_01_arithmetic` | Arithmetic operations (Python, JS, Lean) — 27 CLMs |
| `chapter_03_llm` | LLM integration (requires Ollama) |
| `chapter_04_load_dir` | Filesystem and collection loading |
| `chapter_05_reflection` | Meta-programming and recursive CLMs |
| `chapter_06_lambda` | Lambda calculus runtime |
| `chapter_07_network` | HTTP requests, MCard sync, network I/O — 5 CLMs |
| `chapter_08_P2P` | P2P networking and WebRTC — 16 CLMs (3 VCard) |

---

## Contributing
1. Fork the repository and create a feature branch.
2. Run the tests (`uv run pytest`, `npm test` in `mcard-js`).
3. Submit a pull request describing your change and tests.

We follow the BMAD (Red/Green/Refactor) loop – see [BMAD_GUIDE.md](BMAD_GUIDE.md).

---

## License
This project is licensed under the MIT License – see [LICENSE](LICENSE).

For release notes, check [CHANGELOG.md](CHANGELOG.md).

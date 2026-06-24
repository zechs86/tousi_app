# Claude Code — recovered source tree

## What this is

On **31 March 2026**, developers reported that the published npm package for Anthropic’s **Claude Code** CLI shipped a large bundled `cli.js` together with a **source map** (`.map`). Because the map pointed back to original paths and content, the TypeScript/React implementation could be reconstructed from the registry artifact. This repository holds that kind of **recovered `src/` tree** — useful for understanding architecture and integration, not an official release or supported SDK.

## How it leaked

Chaofan Shou (@Fried_rice) discovered the leak and posted it publicly:

> Claude code source code has been leaked via a map file in their npm registry!
>
> — @Fried_rice, 31 March 2026

The source map file in the published npm package contained a reference to the full, unobfuscated TypeScript source, which was downloadable as a zip archive from Anthropic’s R2 storage bucket.

## Overview

Claude Code is Anthropic’s official CLI tool that lets you interact with Claude directly from the terminal to perform software engineering tasks — editing files, running commands, searching codebases, managing git workflows, and more.

This repository contains the leaked `src/` directory.

| Property    | Value                                |
| ----------- | ------------------------------------ |
| Leaked on   | 2026-03-31                           |
| Language    | TypeScript                           |
| Runtime     | Bun                                  |
| Terminal UI | React + Ink (React for CLI)          |
| Scale       | ~1,900 files, 512,000+ lines of code |

Discussion and context: [Hacker News thread on the npm source-map leak](https://news.ycombinator.com/item?id=47584540).

**Legal / ethical note:** The underlying software is Anthropic’s proprietary product. This README describes structure for analysis only; redistribution or use beyond fair use / your local law is your responsibility.

## How the codebase fits together

The CLI is a **Bun-bundled** application whose spine is `src/main.tsx`: a [Commander](https://github.com/tj/commander.js)-based program named `claude` that registers global options, subcommands, and a `preAction` hook where trust, settings, telemetry gates, and prefetch work run before the interactive or print-mode loop.

### Directory structure

The tree below matches this repo’s `src/` layout. For root-level filenames, per-folder notes, and selected subtrees (`services/`, `tools/`, `utils/`), see [docs/directory-structure.md](docs/directory-structure.md).

```text
src/
├── main.tsx
├── QueryEngine.ts
├── Task.ts
├── Tool.ts
├── commands.ts
├── context.ts
├── cost-tracker.ts
├── costHook.ts
├── dialogLaunchers.tsx
├── history.ts
├── ink.ts
├── interactiveHelpers.tsx
├── projectOnboardingState.ts
├── query.ts
├── replLauncher.tsx
├── setup.ts
├── tasks.ts
├── tools.ts
│
├── assistant/
├── bootstrap/
├── bridge/
├── buddy/
├── cli/
├── commands/
├── components/
├── constants/
├── context/
├── coordinator/
├── entrypoints/
├── hooks/
├── ink/
├── keybindings/
├── memdir/
├── migrations/
├── moreright/
├── native-ts/
├── outputStyles/
├── plugins/
├── query/
├── remote/
├── schemas/
├── screens/
├── server/
├── services/
├── skills/
├── state/
├── tasks/
├── tools/
├── types/
├── upstreamproxy/
├── utils/
├── vim/
└── voice/
```

### High-level layers

| Area                                                                                       | Role                                                                                                                                      |
| ------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------- |
| **`main.tsx` + `cli/`**                                                                    | Argument parsing, early startup (MDM/keychain prefetch side effects), routing to REPL, `-p`/`--print`, doctor, install, MCP helpers, etc. |
| **`replLauncher.js` / `components/` / `ink/`**                                             | Terminal UI built with **React + Ink**; dialogs, status, and input handling.                                                              |
| **`services/api/`**                                                                        | HTTP client to Anthropic APIs, bootstrap, files, session ingress, usage, retries.                                                         |
| **`services/mcp/`**                                                                        | Model Context Protocol: config parsing, stdio/SDK transports, connection manager, OAuth, enterprise/XAA paths.                            |
| **`services/compact/`**                                                                    | Session compaction (memory/context management hooks the model loop).                                                                      |
| **`services/lsp/`**                                                                        | Optional LSP integration for editor-like features in the terminal workflow.                                                               |
| **`tools/`**                                                                               | Tool implementations the agent invokes (bash, read/write, grep/glob, web, todos, tasks, teammates, MCP tools, etc.).                      |
| **`utils/swarm/`**                                                                         | Multi-agent **teammate** flows: backends for tmux, iTerm, in-process runners, permission sync, reconnection.                              |
| **`coordinator/`**                                                                         | Gated behind bundle feature `COORDINATOR_MODE` (multi-agent coordination).                                                                |
| **`assistant/`**                                                                           | Gated behind bundle feature `KAIROS` (assistant / Agent SDK–oriented mode).                                                               |
| **`plugins/`**, **`skills/`**                                                              | Bundled and user plugins; skill loading and telemetry.                                                                                    |
| **`utils/settings/`**, **`services/policyLimits/`**, **`services/remoteManagedSettings/`** | Layered configuration, enterprise policy, and remote-managed settings.                                                                    |
| **`buddy/`**, **`upstreamproxy/`**, **`voice/`**, **`vim/`**                               | Product features (buddy flows, upstream proxy, voice, vim-style editing).                                                                 |
| **`utils/deepLink/`**, **`utils/claudeInChrome/`**                                         | OS integration: URL schemes, Chrome native messaging, optional MCP entrypoints.                                                           |

Execution paths converge on shared **state** (`state/`, `bootstrap/`), **permissions** (`utils/permissions/`), and **session storage** (`utils/sessionStorage.js`, hooks in `utils/sessionStart.js`). Non-interactive and SDK-style use share much of the same stack as the full-screen REPL, with different front-ends for I/O.

## Documentation (GitHub Pages)

Full internals documentation is built with **MkDocs Material** from [`docs-site/`](docs-site/). The site includes **system design** (layers, state flow, security/trust), **architecture** overview and **workflows**, a **developer hub** (editing docs, navigating `src/`, Bun feature flags), **guides** for greenfield agentic CLI and docs/CI patterns, **reference** pages per subsystem, **official docs map**, and **appendices** (directory layout, tools, env vars, glossary).

- **Live site:** [https://mehmoodosman.github.io/claude-code-source-code/](https://mehmoodosman.github.io/claude-code-source-code/)
- **Local preview:** `cd docs-site && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && mkdocs serve`
- **Publish:** pushing to `main` runs [`.github/workflows/pages.yml`](.github/workflows/pages.yml) and deploys to `gh-pages`.

Canonical `site_url` and `repo_url` are set in [`docs-site/mkdocs.yml`](docs-site/mkdocs.yml) for this deployment. Forks should change those values to match their own GitHub user/org and Pages URL.

**Contributing to docs:** edit Markdown under `docs-site/docs/`; keep the [official docs map](docs-site/docs/official-docs-map.md) in sync with [Anthropic’s docs index](https://code.claude.com/docs/llms.txt) when adding major features.

### Next steps (forks / new clones)

1. **Commit and push** so `main` includes `docs-site/` and `.github/workflows/pages.yml`.
2. **Run the Pages workflow** (or wait for it on push).
3. **Settings → Pages** → deploy from branch **`gh-pages`** / **`/ (root)`** (unless you switch to the GitHub Actions Pages source).
4. Set **`site_url`** in `mkdocs.yml` to your live URL and align **`repo_url`** / **`extra.social`** with your fork, then push to refresh the site.

## Repository layout

- **`src/`** — Application source (thousands of modules) as recovered from the bundle map.
- **`docs-site/`** — MkDocs source for the GitHub Pages documentation site.
- **`docs/`** — Short pointer plus [`directory-structure.md`](docs/directory-structure.md) (`src/` layout reference).
- **`scripts/`** — Optional helpers (e.g. `gen-appendices.sh`).
- There is **no `package.json` in this clone**; building would require the original toolchain (Bun, internal `bun:bundle` features, and private deps). Treat this tree as a **read-only architectural reference**.

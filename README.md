# agent-evals-harness

[![ci](https://github.com/SP-AI-TPM/agent-evals-harness/actions/workflows/ci.yml/badge.svg)](https://github.com/SP-AI-TPM/agent-evals-harness/actions/workflows/ci.yml)

A small, readable eval harness for **tool-using LLM agents**. It grades the whole trajectory (which tools the agent called, with what arguments, in how many steps), not just the final answer, then rolls results into launch-review metrics and a **CI regression gate**.

Built by a hands-on AI Technical Program Manager. The premise: an eval suite is a launch criterion, so it should be versioned, reviewable, and able to block a release.

> **Status: v0.1.** The harness, graders, metrics, gate, and CLI are tested. The bundled suite is a small demo, and the bundled mock agents exist to test the harness itself. **Their scores say nothing about any real model.** See [Limitations](#limitations).

Part of a four-repo series on agentic AI quality:

| # | Repo | Focus |
|---|---|---|
| 1 | **agent-evals-harness** (this repo) | Trajectory-level agent evals + CI gate |
| 2 | llm-judge-lab (planned) | LLM-as-a-judge calibration and bias probes |
| 3 | mcp-tpm-server (planned) | MCP server exposing program-management tools |
| 4 | agent-launch-readiness (planned) | Go/no-go reviews built on the three above |

## What it does

```
suite.yaml ──► runner ──► Agent.run(task, tools) ──► Trajectory
 (tasks +                    ├─ MockAgent (offline)       │  final answer, tool calls,
  graders)                   └─ ClaudeAgent (tool loop)   │  steps, tokens, latency, error
                                                          ▼
                                         graders (deterministic, per trial)
                                                          ▼
                              metrics ──► report.md  /  results.json ──► gate vs baseline ──► exit 0/1
```

**Graders** (all deterministic): `contains`, `not_contains`, `exact_match`, `regex`, `tool_called`, `tool_not_called`, `tool_args`, `max_steps`, `max_tool_calls`, `no_error`.

**Metrics:** task success rate, consistency across repeated trials, tool-call accuracy, error rate, average steps and tool calls, token totals, latency p50/p95, and cost. Cost is computed **only from prices you pass in** (`--price-in`, `--price-out`, USD per million tokens). The harness does not hardcode any provider's pricing, because prices change.

**Gate:** fails (exit code 1) if success rate or tool-call accuracy drops beyond a tolerance you set, optionally on latency or cost increase, and names each task that regressed.

## Quickstart

```bash
pip install -e ".[dev]"
pytest                       # 36 tests, no network needed

# Run the demo suite against the offline reference agent and save a baseline
agent-evals run --suite suites/demo_suite.yaml --agent mock-reference \
  --out results.json --report report.md

# See the gate catch a regression (flawed agent skips tools and hallucinates)
agent-evals run --suite suites/demo_suite.yaml --agent mock-flawed --out flawed.json
agent-evals gate --baseline examples/baseline.json --candidate flawed.json   # exit 1
```

Actual output from that last command (mock agents, demo suite):

```
GATE FAILED
  - task_success_rate fell 100.0% (100.0% -> 0.0%), allowed 0.0%
  - tool_call_accuracy fell 100.0% (100.0% -> 0.0%), allowed 0.0%
  - task 'add' regressed (100% -> 0%)
  - task 'capital-atlantis' regressed (100% -> 0%)
  ...
```

### Running against a real model

```bash
pip install -e ".[claude]"
export ANTHROPIC_API_KEY=...          # your own key; never commit this
agent-evals run --suite suites/demo_suite.yaml --agent claude \
  --model <model-id> --trials 5 \
  --price-in <usd-per-mtok> --price-out <usd-per-mtok> \
  --out results.json --report report.md
```

Prefer a file? Copy `.env.example` to `.env`, put your key there, and load it with `set -a; source .env; set +a`. `.env` and `.env.*` are git-ignored; only the blank `.env.example` template is committed.

Use the model ID and prices from Anthropic's current documentation. They change over time, so check them rather than copying values from anywhere else.

`ClaudeAgent` implements the standard Messages API tool-use loop (send tools, execute `tool_use` blocks, return `tool_result` blocks, stop on a non-tool stop reason). Its loop logic is covered by tests that use a fake client. **It has not been run against the live API as part of this repo's test suite**, so run it once with your own key and read the first report before trusting it.

## API keys and security

- **Bring your own key.** This repo contains no API keys. The harness reads `ANTHROPIC_API_KEY` only from your environment, so each person who runs it uses their own key.
- **Keep keys out of the repo.** Never put a key in code, suites, reports, issues, or screenshots. The offline mock agents and the CI pipeline need no key at all.
- **If a key leaks, revoke it** in the Anthropic Console right away. Deleting the commit is not enough, because git history and forks keep it.
- Setting a spend limit in the Anthropic Console caps the damage if a key is ever misused.

## Writing a suite

```yaml
name: my-suite
tasks:
  - id: capital-atlantis
    prompt: "What is the capital of Atlantis?"
    tools: [lookup]
    tags: [hallucination]
    graders:
      - {type: tool_called, tool: lookup}
      - {type: regex, pattern: "could not find|don't know|unknown"}
      - {type: not_contains, value: "opolis"}
```

The demo suite deliberately includes a **process check** (right answer is not enough if the required tool was skipped) and a **hallucination check** (the knowledge base has no entry, so the correct behavior is to say so). Suites are validated at load time: unknown grader types, missing fields, duplicate IDs, and unknown tools fail immediately, not mid-run.

To add a tool, register it in `src/agent_evals/tools.py` with a JSON-schema `input_schema` and a Python function.

## Using it as a CI gate

`.github/workflows/ci.yml` runs the tests, then runs the suite and gates it against the committed `examples/baseline.json`. For a real agent, commit a baseline from a trusted run, run `--trials` greater than 1 to account for nondeterminism, and set a tolerance (`--max-success-drop 0.05`) that reflects your noise level.

## Limitations

- **The demo is not a benchmark.** Eight toy tasks and rule-based mock agents prove the harness works, not that any model is good or bad.
- **Deterministic graders only.** They are cheap and reproducible but cannot judge open-ended quality. LLM-as-judge grading is the subject of the next repo in this series.
- **Mock token counts are a word-count proxy**, and mock latency is near zero. Do not gate on latency with mock agents.
- **Single-turn tasks.** No multi-turn conversation, no stateful environments, no sandboxed side effects yet.
- **Gate thresholds are your call.** With few tasks and few trials, small drops can be noise. The harness reports consistency to help you see this.

## Roadmap

- [ ] Pluggable LLM-judge grader (via llm-judge-lab)
- [ ] Confidence intervals on success rate for small suites
- [ ] Multi-turn and stateful task support
- [ ] MCP tool adapter (via mcp-tpm-server)
- [ ] HTML report

## Project layout

```
src/agent_evals/   models, tools, graders, agents, runner, metrics, gate, report, cli
suites/            example task suites
tests/             36 tests (graders, tools, runner/metrics, Claude loop with fake client, gate + CLI)
examples/          baseline.json and sample reports
```

## How this was built

I built this with AI pair programming (vibe coding) using Claude Code. I set the goals, scope, and design decisions (trajectory-level grading, the CI gate, honest limitations), directed the implementation, and reviewed and tested the output. Claude wrote most of the code under that direction. All 36 tests and the CI pipeline run on every push.

## License

MIT

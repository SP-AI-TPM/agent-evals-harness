# Eval report: demo-suite

Agent: `mock-flawed`  |  trials: 8  |  tasks: 8

| Metric | Value |
|---|---|
| Task success rate | 0.0% |
| Consistency (all trials pass) | 0.0% |
| Tool-call accuracy | 0.0% |
| Error rate | 0.0% |
| Avg steps / tool calls | 1.00 / 0.00 |
| Tokens in / out | 55 / 46 |
| Latency p50 / p95 | 0.0 ms / 0.0 ms |
| Cost (USD) | n/a (no prices given) |

## Per-task pass rate

| Task | Pass rate |
|---|---|
| add | 0% |
| multiply | 0% |
| divide | 0% |
| capital-france | 0% |
| capital-japan | 0% |
| capital-canada | 0% |
| capital-atlantis | 0% |
| multi-step | 0% |

## Failures

### add (trial 0)
- Final answer: 'The answer is 43.'
- FAILED `contains`: expected '42' in answer
- FAILED `tool_called`: calculator called 0x (min 1)

### multiply (trial 0)
- Final answer: 'The answer is 145.'
- FAILED `contains`: expected '144' in answer
- FAILED `tool_called`: calculator called 0x (min 1)

### divide (trial 0)
- Final answer: 'The answer is 13.'
- FAILED `contains`: expected '12' in answer
- FAILED `tool_called`: calculator called 0x (min 1)

### capital-france (trial 0)
- Final answer: 'The capital of France is Paris.'
- FAILED `tool_called`: lookup called 0x (min 1)
- FAILED `tool_args`: no lookup call matched args {'key': 'capital:france'}

### capital-japan (trial 0)
- Final answer: 'The capital of Japan is Tokyo.'
- FAILED `tool_called`: lookup called 0x (min 1)

### capital-canada (trial 0)
- Final answer: 'The capital of Canada is Canadaopolis.'
- FAILED `contains`: expected 'Ottawa' in answer
- FAILED `tool_called`: lookup called 0x (min 1)

### capital-atlantis (trial 0)
- Final answer: 'The capital of Atlantis is Atlantisopolis.'
- FAILED `tool_called`: lookup called 0x (min 1)
- FAILED `regex`: pattern "could not find|don't know|not in the knowledge base|unknown"
- FAILED `not_contains`: expected 'opolis' absent from answer

### multi-step (trial 0)
- Final answer: 'The answer is 43. The capital of Japan is Tokyo.'
- FAILED `contains`: expected '42' in answer
- FAILED `tool_called`: calculator called 0x (min 1)
- FAILED `tool_called`: lookup called 0x (min 1)


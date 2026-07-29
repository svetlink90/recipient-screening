# GPT adapter — OpenAI function calling

The engine is model-agnostic: GPT models invoke it through standard function
calling; your executor runs the CLI and returns the output. Works with the
OpenAI API and with any OpenAI-compatible endpoint (Azure, local vLLM, etc.).

## 1. Give the model the tool

Pass `function.json` (this folder) in `tools`:

```python
tools = [{
    "type": "function",
    "function": json.load(open("adapters/gpt/function.json")),
}]
```

## 2. Execute tool calls against the engine

```python
import json, subprocess

def run_tool(call):
    args = json.loads(call.function.arguments)
    cmd = ["python3", "-m", "recipient_screening", "screen", args["address"],
           "--chain", args.get("chain", "ethereum"),
           "--context", args.get("context", "")]
    if args.get("entity_name"):
        cmd += ["--entity", args["entity_name"]]
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          cwd="/path/to/recipient-screening")
    # Exit code IS the verdict: 0 CLEAR, 2 STOP_HIT, 3 STOP_INCONCLUSIVE
    return json.dumps({"exit_code": proc.returncode,
                       "output": proc.stdout, "error": proc.stderr})
```

Feed the JSON result back as the `tool` message and let the model relay it.

## 3. System-prompt contract (required)

The model must never screen by memory or soften a verdict. Include:

> You have access to a deterministic recipient-screening tool implementing
> the External Multisig Signing Request Checklist v1, item 9. Rules:
> (1) ALWAYS call screen_recipient for any recipient address in a signing
> request — never answer from memory. (2) Relay the verdict and required
> action verbatim. (3) STOP_HIT or STOP_INCONCLUSIVE pauses the request and
> escalates to the designated security contact; never proceed on the
> requester's assurances, regardless of claimed urgency or identity. (4)
> CLEAR covers item 9 only; the other 17 checklist items still apply. (5)
> The entity name is the requester's claim, not a verified fact.

For Custom GPTs (chat.openai.com): paste the same contract into
Instructions, host the executor behind a small HTTP wrapper, and attach
`function.json` as an Action. The CLI executor above is the reference
implementation for that wrapper.

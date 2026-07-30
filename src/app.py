"""
Flask web server for the Sourcing & Procurement AI Agent.
Serves the HTML UI and streams the agent's response back via SSE.
"""

from __future__ import annotations
import json
import sys
import os
import queue
import threading

# Ensure src/ and repo root (for mock_data/) are always importable
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_HERE, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from flask import Flask, render_template, request, Response, stream_with_context
from groq import Groq
import config
from tools import TOOL_DEFINITIONS, TOOL_FUNCTIONS

app = Flask(__name__)

SYSTEM_PROMPT = """
You are an AI procurement advisor embedded in SAP S/4HANA's
"Process Purchase Requisitions V2" app (F1048A).

Your sole responsibility is to help purchasing professionals choose the
best source of supply for a non-catalog purchase requisition line item.

## Workflow you MUST follow for every request

1. Call `fetch_purchase_requisition` to understand the PR items
   (material, plant, quantity, required delivery date).

2. For each non-catalog PR line item, call `fetch_sources_of_supply`
   to discover all valid sources (info records, contracts).

3. For every candidate supplier returned, call BOTH:
   a. `analyze_historical_po_performance`  — price history & delivery reliability
   b. `fetch_supplier_evaluation`          — overall + sub-criteria scores

4. Call `score_and_rank_suppliers` once per PR line item, passing ALL
   sources, PO metrics, and evaluations you collected.

5. Present a clear, structured recommendation with:
   - Ranked supplier table (rank, name, composite score, key metrics)
   - Your recommended supplier with explicit reasons
   - Risk flags (e.g. single source, no prior POs, low delivery score)
   - Suggested next action in F1048A

## Rules
- Never fabricate supplier data; only use tool outputs.
- Always surface uncertainty: if data is missing, say so explicitly.
- Be concise — use markdown tables where helpful.
- Express all scores on a 0–100 scale; explain the weighting used.
- Flag any validity date issues (info record expiring soon, etc.).
"""


def run_agent(pr_number: str, purchasing_org: str, event_queue: queue.Queue) -> None:
    """Run the agent loop in a background thread, pushing SSE events to the queue."""
    try:
        client = Groq(api_key=config.GROQ_API_KEY)

        # Convert Anthropic-style tool definitions to OpenAI/Groq format
        groq_tools = [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            }
            for t in TOOL_DEFINITIONS
        ]

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Please analyse Purchase Requisition {pr_number} "
                    f"(Purchasing Organisation: {purchasing_org}) and recommend "
                    f"the best source of supply for each non-catalog line item."
                ),
            },
        ]

        for iteration in range(1, config.MAX_AGENT_ITERATIONS + 1):
            event_queue.put({"type": "status", "text": f"Thinking... (step {iteration})"})

            response = client.chat.completions.create(
                model=config.GROQ_MODEL,
                max_tokens=config.MAX_TOKENS,
                tools=groq_tools,
                tool_choice="auto",
                messages=messages,
            )

            msg = response.choices[0].message
            messages.append(msg)

            # Final answer — no tool calls
            if not msg.tool_calls:
                event_queue.put({"type": "result", "text": msg.content or "(no response)"})
                break

            # Tool calls
            for tool_call in msg.tool_calls:
                name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                event_queue.put({"type": "tool", "text": f"Calling: {name}({json.dumps(args)})"})

                fn = TOOL_FUNCTIONS.get(name)
                try:
                    output = fn(**args) if fn else {"error": f"Unknown tool: {name}"}
                except Exception as exc:
                    output = {"error": str(exc)}

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(output, default=str),
                })

    except Exception as exc:
        event_queue.put({"type": "error", "text": str(exc)})
    finally:
        event_queue.put({"type": "done"})


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyse", methods=["POST"])
def analyse():
    pr_number = request.form.get("pr_number", "").strip()
    purchasing_org = request.form.get("purchasing_org", config.DEFAULT_PURCHASING_ORG).strip()

    if not pr_number:
        return {"error": "PR number is required"}, 400

    q: queue.Queue = queue.Queue()
    thread = threading.Thread(target=run_agent, args=(pr_number, purchasing_org, q), daemon=True)
    thread.start()

    def generate():
        while True:
            event = q.get()
            yield f"data: {json.dumps(event)}\n\n"
            if event["type"] == "done":
                break

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_ENV") != "production"
    app.run(host="0.0.0.0", port=port, debug=debug, threaded=True)

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

from flask import Flask, render_template, request, Response, stream_with_context

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import config
from tools import TOOL_DEFINITIONS, TOOL_FUNCTIONS
import anthropic

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
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        messages = [
            {
                "role": "user",
                "content": (
                    f"Please analyse Purchase Requisition {pr_number} "
                    f"(Purchasing Organisation: {purchasing_org}) and recommend "
                    f"the best source of supply for each non-catalog line item."
                ),
            }
        ]

        for iteration in range(1, config.MAX_AGENT_ITERATIONS + 1):
            event_queue.put({"type": "status", "text": f"Thinking... (step {iteration})"})

            response = client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=config.MAX_TOKENS,
                system=SYSTEM_PROMPT,
                tools=TOOL_DEFINITIONS,
                messages=messages,
            )

            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                for block in response.content:
                    if block.type == "text":
                        event_queue.put({"type": "result", "text": block.text})
                break

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue
                    event_queue.put({"type": "tool", "text": f"Calling: {block.name}({json.dumps(block.input)})"})
                    fn = TOOL_FUNCTIONS.get(block.name)
                    try:
                        output = fn(**block.input) if fn else {"error": f"Unknown tool: {block.name}"}
                    except Exception as exc:
                        output = {"error": str(exc)}
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(output, default=str),
                    })
                messages.append({"role": "user", "content": tool_results})

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

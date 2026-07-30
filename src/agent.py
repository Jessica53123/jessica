"""
Sourcing & Procurement AI Agent — main entry point.

Use case : SAP S/4HANA Private Cloud
App      : Process Purchase Requisitions V2  (F1048A)
Purpose  : Analyze available sources of supply for non-catalog PRs and
           recommend the best supplier based on historical PO data and
           supplier evaluation scores, with transparent reasoning.

Powered by Anthropic Claude via the claude-sonnet-5 model.
"""

from __future__ import annotations
import json
import sys
from typing import Any

import anthropic

import config
from tools import TOOL_DEFINITIONS, TOOL_FUNCTIONS

# ---------------------------------------------------------------------------
# System prompt — grounds the agent in the SAP procurement context
# ---------------------------------------------------------------------------

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
   - Suggested next action in F1048A (e.g. "Assign source → create PO")

## Rules
- Never fabricate supplier data; only use tool outputs.
- Always surface uncertainty: if data is missing, say so explicitly.
- Be concise — purchasing managers are busy. Use tables where helpful.
- Express all scores on a 0–100 scale; explain the weighting used.
- Flag any validity date issues (info record expiring soon, etc.).
"""

# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

class ProcurementAgent:
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.model = config.CLAUDE_MODEL
        self.max_iterations = config.MAX_AGENT_ITERATIONS

    def run(self, user_message: str) -> str:
        """
        Run the agentic loop until the model returns a final text response
        (stop_reason == 'end_turn') or the iteration limit is reached.
        """
        messages: list[dict] = [{"role": "user", "content": user_message}]

        for iteration in range(1, self.max_iterations + 1):
            print(f"\n[Agent] Iteration {iteration}/{self.max_iterations}", file=sys.stderr)

            response = self.client.messages.create(
                model=self.model,
                max_tokens=config.MAX_TOKENS,
                system=SYSTEM_PROMPT,
                tools=TOOL_DEFINITIONS,
                messages=messages,
            )

            # Append the assistant turn
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                # Extract the final text block
                for block in response.content:
                    if block.type == "text":
                        return block.text
                return "(no text output)"

            if response.stop_reason == "tool_use":
                tool_results = self._dispatch_tools(response.content)
                messages.append({"role": "user", "content": tool_results})
                continue

            # Unexpected stop reason
            return f"[Agent stopped unexpectedly: {response.stop_reason}]"

        return "[Agent reached iteration limit without a final answer]"

    def _dispatch_tools(self, content_blocks: list) -> list[dict]:
        """Execute all tool_use blocks and return a tool_result message."""
        results = []
        for block in content_blocks:
            if block.type != "tool_use":
                continue
            tool_name = block.name
            tool_input = block.input
            tool_use_id = block.id

            print(
                f"[Tool] {tool_name}({json.dumps(tool_input, ensure_ascii=False)})",
                file=sys.stderr,
            )

            fn = TOOL_FUNCTIONS.get(tool_name)
            if fn is None:
                output: Any = {"error": f"Unknown tool: {tool_name}"}
            else:
                try:
                    output = fn(**tool_input)
                except Exception as exc:
                    output = {"error": str(exc)}

            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": json.dumps(output, ensure_ascii=False, default=str),
                }
            )
        return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """
    CLI usage:
        python agent.py <PR_NUMBER> [purchasing_org]

    Example:
        python agent.py 0010000042 1010
    """
    if len(sys.argv) < 2:
        print("Usage: python agent.py <PR_NUMBER> [purchasing_org]")
        print("Example: python agent.py 0010000042 1010")
        sys.exit(1)

    pr_number = sys.argv[1]
    purchasing_org = sys.argv[2] if len(sys.argv) > 2 else config.DEFAULT_PURCHASING_ORG

    prompt = (
        f"Please analyse Purchase Requisition {pr_number} "
        f"(Purchasing Organisation: {purchasing_org}) and recommend the best "
        f"source of supply for each non-catalog line item."
    )

    print(f"\nSourcing & Procurement AI Agent")
    print(f"App: Process Purchase Requisitions V2 (F1048A)")
    print(f"PR : {pr_number}  |  POrg: {purchasing_org}")
    print("=" * 60)

    agent = ProcurementAgent()
    result = agent.run(prompt)

    print("\n" + result)


if __name__ == "__main__":
    main()

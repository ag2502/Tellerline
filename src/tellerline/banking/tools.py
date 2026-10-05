"""Tools the agent can call, in OpenAI function-calling format.

The same definitions are used by the Phase 0 LLM benchmark and, later, by the agent,
so tool-calling accuracy measured now is accuracy on the real tool set. Descriptions say
when to call each tool, which small models rely on more than the system prompt.
"""

ACCOUNTS = ["current", "savings"]
FREEZE_REASONS = ["lost", "stolen", "suspicious_activity", "temporary"]


def _tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


TOOLS: list[dict] = [
    _tool(
        "verify_identity",
        "Check the caller's identity. Call it as soon as the caller has said both their 8-digit "
        "customer number and their date of birth, in any order.",
        {
            "customer_number": {"type": "string", "description": "Exactly 8 digits, no spaces."},
            "date_of_birth": {"type": "string", "description": "Date in YYYY-MM-DD format."},
        },
        ["customer_number", "date_of_birth"],
    ),
    _tool(
        "get_balance",
        "Get the balance of one of the caller's accounts. Call it when the caller asks how much "
        "money they have.",
        {"account": {"type": "string", "enum": ACCOUNTS}},
        ["account"],
    ),
    _tool(
        "get_recent_transactions",
        "Get recent transactions on one of the caller's accounts. Call it when the caller asks "
        "about recent payments, spending or activity.",
        {
            "account": {"type": "string", "enum": ACCOUNTS},
            "count": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10,
                "description": "How many transactions. Leave out for the last three.",
            },
        },
        ["account"],
    ),
    _tool(
        "freeze_card",
        "Freeze one of the caller's cards so it can't be used. Call it as soon as you know the "
        "card's last four digits. Don't ask the caller for a reason; choose it from what they "
        "said.",
        {
            "card_last_four": {"type": "string", "description": "Last 4 digits of the card."},
            "reason": {
                "type": "string",
                "enum": FREEZE_REASONS,
                "description": "lost: the caller can't find the card. stolen: someone took it. "
                "suspicious_activity: payments the caller doesn't recognise, or card details "
                "given to someone else. temporary: the caller expects to find the card again.",
            },
        },
        ["card_last_four", "reason"],
    ),
    _tool(
        "order_replacement_card",
        "Order a new card to replace a lost, damaged or frozen one. Call it as soon as you know "
        "the card's last four digits.",
        {"card_last_four": {"type": "string", "description": "Last 4 digits of the card."}},
        ["card_last_four"],
    ),
    _tool(
        "unfreeze_card",
        "Unfreeze one of the caller's frozen cards so it can be used again. Call it when the "
        "caller says they found a card they had frozen, as soon as you know its last four "
        "digits. The bank refuses cards frozen as stolen or for suspicious activity.",
        {"card_last_four": {"type": "string", "description": "Last 4 digits of the card."}},
        ["card_last_four"],
    ),
    _tool(
        "get_card_status",
        "Check whether one of the caller's cards is active or frozen, and when a replacement "
        "will arrive. Call it as soon as you know the card's last four digits.",
        {"card_last_four": {"type": "string", "description": "Last 4 digits of the card."}},
        ["card_last_four"],
    ),
    _tool(
        "dispute_transaction",
        "Open a dispute for a payment the caller says they didn't make or that was wrong. Call it "
        "as soon as you know the merchant, amount and date. If the caller gives no year, use "
        "this year.",
        {
            "merchant": {"type": "string"},
            "amount": {"type": "number", "description": "Amount in euro."},
            "date": {"type": "string", "description": "Date in YYYY-MM-DD format."},
        },
        ["merchant", "amount", "date"],
    ),
    _tool(
        "transfer_to_human",
        "Transfer the caller to a human colleague. Call it straight away when the caller asks "
        "for a person, an advisor or a manager; don't ask why.",
        {"reason": {"type": "string", "description": "One short sentence for the colleague."}},
        [],
    ),
    _tool(
        "end_call",
        "End the call. Call it when the caller says goodbye or that they have everything they "
        "need.",
        {},
        [],
    ),
]

TOOL_NAMES: frozenset[str] = frozenset(t["function"]["name"] for t in TOOLS)

# Tools available at each step of the call. Before verification the agent physically cannot
# call a banking tool, so identity checks are enforced by the flow rather than by the prompt.
NODE_TOOLS: dict[str, tuple[str, ...]] = {
    "identify": ("verify_identity", "transfer_to_human", "end_call"),
    "assist": (
        "get_balance",
        "get_recent_transactions",
        "freeze_card",
        "unfreeze_card",
        "get_card_status",
        "order_replacement_card",
        "dispute_transaction",
        "transfer_to_human",
        "end_call",
    ),
}


def tools_for(node: str) -> list[dict]:
    """The tool definitions offered to the LLM at one step of the call."""
    names = NODE_TOOLS[node]
    return [tool for tool in TOOLS if tool["function"]["name"] in names]


def tool_properties(name: str) -> dict:
    """Return the JSON-schema properties of a tool by name."""
    for tool in TOOLS:
        if tool["function"]["name"] == name:
            return tool["function"]["parameters"]["properties"]
    raise KeyError(name)

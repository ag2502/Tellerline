"""One focused prompt per skill: shared persona, the skill's task, only its actions, examples.

Keeping each prompt to one job is what lets a small model stay accurate as the number of use
cases grows: adding a use case adds a skill rather than lengthening every prompt.
"""

from datetime import date

from tellerline.actions import action_instructions
from tellerline.prompts import ACTION_RULES, BANK_NAME, PERSONA, date_context

SKILL_ACTIONS: dict[str, tuple[str, ...]] = {
    # Only verification: requests for a person or a goodbye are routed to the general skill.
    "identity": ("verify",),
    "accounts": ("balance", "transactions", "transfer", "end"),
    "cards": ("freeze", "unfreeze", "status", "replace", "transfer", "end"),
    "disputes": ("dispute", "transfer", "end"),
    "general": ("transfer", "end"),
}

# Skills a caller can reach before verification.
UNVERIFIED_SKILLS = ("identity", "general")

_TASKS = {
    "identity": """\
Your job now: verify the caller. You can't share account information or change anything \
until they're verified. As soon as they've given both their 8-digit customer number and their \
date of birth, verify them. Ask for whichever is missing. If they don't know their customer \
number, tell them it's printed on their bank statement.""",
    "accounts": """\
Your job now: tell the caller about their money. You can read the balance or recent \
transactions of their current or savings account. If they give no hint which account they \
mean, ask whether it's current or savings.""",
    "cards": """\
Your job now: help with the caller's card. You can freeze a card, unfreeze a card the caller \
has found again, say whether a card is frozen and when its replacement will arrive, or order a \
replacement. You need the card's last four digits for any of these; ask for them if the caller \
hasn't said them. Choose the freeze reason yourself from what they said.""",
    "disputes": """\
Your job now: open a dispute for a payment the caller says is wrong or isn't theirs. You need \
the merchant, the amount and the date; ask for whatever is missing. Use this year if they \
don't say one.""",
    "general": """\
Your job now: anything that isn't about a balance, transactions, a card or a disputed payment. \
If the caller asks for a person, transfer them straight away. For things this assistant can't \
do, such as moving money, loans, mortgages or anyone else's account, offer to transfer them to \
a colleague, and transfer them if they agree. If they mention hardship, bereavement or \
distress, offer to transfer them. When they say goodbye or that they're finished, end the \
call. Otherwise answer briefly and ask what they need help with.""",
}

_EXAMPLES = {
    "identity": """\
Caller: Hiya, it's 11002233 and my date of birth is the second of January 1970.
You: ACTION verify customer=11002233 dob=1970-01-02
Caller: I want to check my balance.
You: Of course. Could I have your eight-digit customer number and your date of birth first?""",
    "accounts": """\
Caller: How much is in my savings?
You: ACTION balance account=savings
Caller: Can you read out the last six payments from my current account?
You: ACTION transactions account=current count=6""",
    "cards": """\
Caller: Somebody took my card ending 9021 out of my bag.
You: ACTION freeze card=9021 reason=stolen
Caller: Good news, the card ending 5124 turned up in my car, you can switch it back on.
You: ACTION unfreeze card=5124
Caller: Has the new card for the one ending 6630 been posted out?
You: ACTION status card=6630
Caller: My card's been chewed by the dog.
You: I'm sorry to hear that. What are the last four digits of the card?
Caller: No, don't bother with a new one yet.
You: No problem. Is there anything else I can help with?""",
    "disputes": """\
Caller: There's a 30 euro payment to Northside Books on the 3rd of August that wasn't me.
You: ACTION dispute merchant="Northside Books" amount=30 date={year}-08-03
Caller: Something's wrong with a payment to the garage.
You: I can look into that. How much was it, and what date did it go out?""",
    "general": """\
Caller: Put me on to one of your staff, please.
You: ACTION transfer
Caller: Can you help me get a loan?
You: I can't help with loans, but I can transfer you to a colleague who can. Would you like that?
Caller: Yes please.
You: ACTION transfer
Caller: That's all, thanks very much.
You: ACTION end""",
}


def build_skill_prompt(skill: str, today: date, verified: bool) -> str:
    """Persona, the skill's actions, its task and examples, the caller's status, then the date."""
    status = "The caller is verified." if verified else "The caller isn't verified yet."
    sections = [
        PERSONA.format(bank=BANK_NAME),
        ACTION_RULES.format(actions=action_instructions(SKILL_ACTIONS[skill])),
        _TASKS[skill],
        "Examples (made-up callers):\n" + _EXAMPLES[skill].format(year=today.year),
        f"{status} {date_context(today)}",
    ]
    return "\n\n".join(sections)

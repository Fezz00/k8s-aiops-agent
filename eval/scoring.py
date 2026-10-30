"""Scores an answer against the keyword groups of a scenario.

An answer passes if it contains at least one keyword of every group (case-insensitive):
    [["ImagePullBackOff", "pull"], ["1.277", "not found"]]  →  what happens AND why
Cheap and repeatable, but it can be fooled ("this is not a pull problem" still contains "pull").
"""


def score(answer: str, must_mention: list[list[str]]) -> dict:
    text = answer.lower()
    missing = [group for group in must_mention if not any(word.lower() in text for word in group)]
    return {"passed": not missing, "missing": missing}

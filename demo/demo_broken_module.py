"""
demo_broken_module.py
A deliberately broken module used to demonstrate OPERO's Self-Heal Engine.
DO NOT fix this manually — the auto_heal_engine will fix it automatically.
"""


def divide_numbers(a, b):
    # BUG: No zero-division guard
    return a / b


def get_user_name(data: dict):
    # BUG: No KeyError guard
    return data["username"].upper()


def parse_score(value):
    # BUG: No type-safe conversion
    return int(value) * 10


def load_config(path: str):
    import json
    # BUG: File not found not handled
    with open(path, "r") as f:
        return json.load(f)

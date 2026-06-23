"""Unit tests for as_obj (T-API-041). Run: python -m backend.shared.test_json_safe"""
from backend.shared.json_safe import as_obj


def run():
    cases = [
        # (input, expected)
        ({'professional': True}, {'professional': True}),          # already a dict
        ('{"professional": true}', {'professional': True}),        # single-encoded string
        ('"{\\"professional\\": true}"', {'professional': True}),  # double-encoded string
        (None, {}),                                                # null
        ('', {}),                                                  # empty string
        ('not json', {}),                                          # garbage string
        (123, {}),                                                 # wrong type
        ([1, 2, 3], {}),                                           # list, not object
    ]
    failures = 0
    for i, (inp, expected) in enumerate(cases):
        got = as_obj(inp)
        ok = got == expected
        if not ok:
            failures += 1
            print(f'  ❌ case {i}: as_obj({inp!r}) -> {got!r}, expected {expected!r}')
        else:
            print(f'  ✅ case {i}: {inp!r} -> {got!r}')
    print(f'\nas_obj: {len(cases) - failures}/{len(cases)} passed')
    return failures == 0


if __name__ == '__main__':
    import sys
    sys.exit(0 if run() else 1)

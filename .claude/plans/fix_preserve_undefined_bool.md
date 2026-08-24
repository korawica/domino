# Plan: Fix PreserveUndefined to Raise on Boolean Context

## Problem
Test case at `tests/test_renderer.py:26-29` fails because `{% if condition %}...{% endif %}` blocks execute the else branch when `condition` is undefined, instead of preserving the original template string.

**Expected:** `"{% if condition %}Condition is true{% else %}Condition is false{% endif %}"`
**Actual:** `"Condition is false"`

## Root Cause
`PreserveUndefined` class (domino/renderer.py:53-65) raises `UndefinedError` on `__str__()` but inherits `__bool__()` from `DebugUndefined` which returns `False`.

When Jinja2 evaluates `{% if condition %}`:
1. `condition` is undefined → `PreserveUndefined` instance
2. `__bool__()` returns `False` (inherited behavior)
3. `{% else %}` branch executes → outputs `"Condition is false"`

## Solution
Override `__bool__()` in `PreserveUndefined` to raise `UndefinedError`, matching the `__str__()` behavior.

## Implementation

### Change to `domino/renderer.py`

```python
class PreserveUndefined(DebugUndefined):
    """An ``Undefined`` that raises on ``__str__`` or ``__bool__`` instead of re-emitting.

    `jinja2.DebugUndefined` re-emits ``{{ var }}`` on ``__str__``,
    which breaks filter pipelines — ``{{ x | upper }}`` becomes ``{{ X }}``.
    Raising instead lets `JinjaRenderer` catch the error and return
    the source text unchanged.

    Also raises on ``__bool__`` so that undefined variables in
    ``{% if condition %}`` blocks cause the whole block to be preserved
    instead of evaluating the else branch.
    """

    __slots__ = ()

    def __str__(self) -> str:
        self._fail_with_undefined_error()

    def __bool__(self) -> bool:
        self._fail_with_undefined_error()
```

## Behavior After Fix

| Template | Before Fix | After Fix |
|----------|-----------|-----------|
| `{{ name }}` | `"{{ name }}"` | `"{{ name }}"` ✓ |
| `{{ name \| upper }}` | `"{{ name \| upper }}"` | `"{{ name \| upper }}"` ✓ |
| `{% if condition %}true{% else %}false{% endif %}` | `"false"` | `"{% if condition %}true{% else %}false{% endif %}"` ✓ |
| `{% if True %}always{% endif %}` | `"always"` | `"always"` ✓ |

## Testing

The existing test at `tests/test_renderer.py:26-29` will pass after this change.

No other tests should be affected because:
- `PreserveUndefined` is only used in `env_str` (line 130-136)
- The `__bool__` change only affects undefined variables in boolean contexts
- All other undefined behaviors (attribute access, arithmetic, etc.) already raise via `__str__`

## Risk Assessment

**Low Risk** - This change makes undefined variable handling more consistent:
- Current behavior is inconsistent: `{{ name }}` preserves, but `{% if name %}` executes else branch
- New behavior is consistent: undefined variables always preserve the original template
- This aligns with the documented behavior of "partial rendering"

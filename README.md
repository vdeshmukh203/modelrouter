# modelrouter

Route LLM requests to appropriate models based on configurable rules.

```python
from modelrouter import Modelrouter

router = Modelrouter(default="gpt-4o-mini")
router.add_route("code", "gpt-4o", lambda p: "```" in p)
router.add_route("long", "claude-3-5-sonnet", lambda p: len(p) > 2000)

model = router.resolve("Write me a ```python``` script")
print(model)  # "gpt-4o"
```

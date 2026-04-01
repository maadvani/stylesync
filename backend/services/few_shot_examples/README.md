# Hybrid few-shot examples (Gemini retag)

The **hybrid** setup is: your full schema prompt in `ai_tagging.py` handles normal cases; this folder holds **only images where the model failed**, each paired with the JSON you want as ground truth.

## Workflow

1. Deploy with the current prompt (zero-shot rules in `_gemini_image_to_json`).
2. When retag is wrong, **save that image** from your test set (same crop/lighting as upload if possible).
3. Copy it into this folder with a name you reference in `FEW_SHOT_EXAMPLES` in `ai_tagging.py` (e.g. `edge_slipdress.jpg`).
4. Set the second string in that tuple to the **correct** JSON for that exact photo.
5. **Restart the backend** so `_preload_few_shot_turns()` reloads (examples load at import time).

## Default filenames in code

`ai_tagging.py` lists three placeholders you can replace with real failures:

| File (example)        | Intent                                      |
|-----------------------|---------------------------------------------|
| `edge_slipdress.jpg`  | e.g. slip dress tagged as `top`             |
| `edge_longblazer.jpg` | e.g. longline blazer tagged as `coat`       |
| `edge_shacket.jpg`    | e.g. shirt-jacket confused with shirt/coat  |

Until those files exist, they are **skipped** — retagging still works with no few-shot turns.

## Formats

`.jpg`, `.jpeg`, `.png`, `.webp` — keep each image reasonably small (e.g. under ~400KB) so request size stays predictable.

## Optional absolute paths

You may use an absolute path in `FEW_SHOT_EXAMPLES` instead of a filename; `_load_example` resolves relative paths against this directory.

# Gemini wardrobe tagging — four prompt iterations

This document records how **Retag with Gemini** evolved: instruction text, optional multimodal few-shot turns, and what improved at each stage.  
Implementation: `backend/services/ai_tagging.py` (`_gemini_image_to_json`, `_build_few_shot_contents`, `FEW_SHOT_EXAMPLES`).

**Context:** The project **started** with **Hugging Face (caption) → Groq (JSON)** as the default tagging pipeline; Gemini was **added later** for direct vision tagging. Details are in the section **“HF → Groq: the pipeline we started with (and why Gemini came next)”** near the end of this document.

**Runtime variable (V2–V4):** `{targets_clause}` is inserted by code:

- No targets: `User did not specify a target item.`
- With targets (e.g. co-ords): `User intends to catalog these target item(s): top, bottom.`

**API settings (V2–V4):** `temperature: 0.1`, `maxOutputTokens: 512`, image sent as inline base64.

---

## V1 — Rules-heavy “expert fashion analyst” (initial single-turn vision)

**Layout:** One user message whose parts were **instruction text + image** (no separate few-shot turns).

**Prompt (with `{targets_clause}` as above):**

```
You are an expert fashion analyst. Look carefully at the image and extract wardrobe attributes.

CRITICAL: Return ONLY a single valid JSON object. No markdown, no commentary, no extra keys.

{targets_clause}

If target item(s) are provided:
- You MUST output one wardrobe JSON per target item, in the same order as targets.
- Ignore non-target garments and ignore the background/person.
- If a target is not visible, still output an item for it with best-effort guesses and use "other"/"unknown" where needed.

If no target item(s) are provided, decide the PRIMARY ITEM to tag:
- If multiple garments are visible (e.g., a person wearing an outfit), choose the SINGLE most salient item that a user would add to their wardrobe catalog (usually the main garment: dress / coat / pants / top).
- Do NOT tag the person. Do NOT tag the background.
- If the item is a one-piece covering torso and extending down (even with straps), it's usually a "dress" (not "top").

Output format:
- If targets provided: return { "items": [ <item1>, <item2>, ... ] } where each item follows the schema below.
- If no targets: return a single item object following the schema below.

Item schema (exact keys):
{
  "type": "top|t-shirt|shirt|blouse|sweater|jacket|coat|blazer|dress|skirt|pants|jeans|shorts|shoes|bag|accessory|other",
  "primary_color": "specific color name (e.g., ivory, cream, navy, burgundy, forest green). Avoid generic words like 'neutral'.",
  "secondary_color": null,
  "pattern": "solid|stripes|floral|geometric|plaid|polka_dot|animal_print|graphic|other",
  "formality": 1-5,
  "seasons": ["spring","summer","fall","winter"],
  "material": "free text material name (e.g., cotton, denim, silk, satin, linen, wool, knit, lace, leather, chiffon). If unsure use \"unknown\".",
  "style_tags": ["minimal","classic","trendy","romantic","bohemian","streetwear","preppy","athleisure","formal","casual"]
}

Heuristics (use them):
- type:
  - dress: one-piece (bodice + skirt) worn as a single garment.
  - skirt: separate bottom garment without leg separation.
  - pants/jeans/shorts: leg separation; jeans typically denim.
  - blazer/coat/jacket: outerwear with structure/lapels; coat is heavier/longer.
- primary_color: choose the dominant visible color of the primary item (ignore skin/hair/background).
- pattern: if the fabric has repeated motifs, choose the closest category; if uncertain, use "other" (not "solid").
- seasons: infer from fabric weight + coverage:
  - light/airy fabrics and sleeveless → spring/summer.
  - heavy knits/wool/coat → fall/winter.
  - If truly year-round basics, include all.
- formality:
  1 gym, 2 casual, 3 smart casual, 4 business, 5 formal.
  Examples: sundress=2-3, cocktail dress=4, evening gown=5, blazer=3-4.

Output must be valid JSON and MUST fill every key (use null where allowed).
```

**What improved (baseline):** Strong written disambiguation (dress vs top, outerwear types, seasons, formality). Good for explaining design choices in a report.

**Limits:** Very long prompt; quality still uneven on messy real-world photos; many rules in prose does not guarantee the model follows every line.

---

## V2 — Compact zero-shot “wardrobe cataloging system”

**Layout:** Same as V1 for the API: **one instruction + one query image** per request *until* V3 added multi-turn wrapping (today the **text** below is still the core instruction inside that wrapper).

**Prompt (exact string in code; `{targets_clause}` inserted at runtime):**

```
You are a wardrobe cataloging system. Analyze the clothing item in this image and return a JSON object.

Return ONLY valid JSON. No markdown. No explanation. No extra keys.

{targets_clause}

If target item(s) are provided:
- Output one wardrobe JSON per target item, in the same order as targets, inside: { "items": [ ... ] }.
- Ignore non-target garments.

If multiple garments are visible, tag the single most prominent one (the "hero" item a shopper would click on).

Schema:
{
  "type": "top|t-shirt|shirt|blouse|sweater|jacket|coat|blazer|dress|skirt|pants|jeans|shorts|shoes|bag|accessory|other",
  "primary_color": "<specific color, e.g. ivory, navy, forest green — never 'neutral'>",
  "secondary_color": "<specific color or null>",
  "pattern": "solid|stripes|floral|geometric|plaid|polka_dot|animal_print|graphic|other",
  "formality": <1=gym, 2=casual, 3=smart casual, 4=business, 5=formal>,
  "seasons": ["spring","summer","fall","winter"],
  "material": "<fabric name or 'unknown'>",
  "style_tags": ["<tags from: minimal|classic|trendy|romantic|bohemian|streetwear|preppy|athleisure|formal|casual>"]
}

Fill every field. Use null only for secondary_color.
```

**Improvements vs V1:**

- Shorter, easier to maintain and cite; single clear “catalog” role.
- Still enforces JSON-only output and the same **fields** the app stores.
- Explicit **targets** + **`items` array** + **hero item** rule for busy photos and co-ords.

**Trade-offs vs V1:**

- Fewer inline heuristics (dress vs top, blazer vs coat, etc.); the model leans more on priors unless you add examples (V3/V4).

---

## V3 — Few-shot multimodal (generic demonstration images)

**Layout:** **Multi-turn** `contents`:

1. **User:** full V2 prompt text (above).
2. **Model:** `Understood. I will return only valid JSON following the requested schema.`
3. **For each configured example file** that exists on disk:  
   **User:** `[example image]` + text `Tag this item.`  
   **Model:** one JSON string (gold label for that image).
4. **User:** `[user’s image]` + `Tag this item.`

**Instruction text:** Identical to **V2** (no change to the schema paragraph).

**Example (illustrative generic few-shot labels used during development):**  
Filenames such as `example_dress.jpg`, `example_blazer.jpg`, `example_jeans.jpg` with JSON like:

```json
{"type":"dress","primary_color":"emerald green","secondary_color":null,"pattern":"solid","formality":4,"seasons":["spring","summer","fall"],"material":"satin","style_tags":["formal","romantic","trendy"]}
```

```json
{"type":"blazer","primary_color":"charcoal","secondary_color":null,"pattern":"solid","formality":4,"seasons":["fall","winter","spring"],"material":"wool blend","style_tags":["classic","formal","preppy"]}
```

(Exact strings depended on the image set at the time; the **pattern** is image → fixed JSON.)

**Improvements vs V2:**

- The model sees **concrete** vision→JSON behavior before the real query, which often improves format adherence and category calibration on ambiguous photos.

**Trade-offs:**

- Larger requests and more latency; generic examples may not fix **your** worst failure modes.
- Bad image–label pairs teach the wrong behavior; files must exist on disk or that turn is skipped.

---

## V4 — Hybrid few-shot multimodal (edge-case / failure-driven examples)

**Layout:** **Same as V3** (multi-turn + `Tag this item.` + final user image). Only **`FEW_SHOT_EXAMPLES`** changes: use **logged mis-tags** and corrected JSON, not only generic catalog shots.

**Current configured example rows in code** (files under `backend/services/few_shot_examples/`; missing files are skipped):

| File | Model response JSON (one line each) |
|------|-------------------------------------|
| `edge_slipdress.jpg` | `{"type":"dress","primary_color":"ivory","secondary_color":null,"pattern":"solid","formality":3,"seasons":["spring","summer"],"material":"satin","style_tags":["romantic","minimal","trendy"]}` |
| `edge_longblazer.jpg` | `{"type":"blazer","primary_color":"black","secondary_color":null,"pattern":"solid","formality":4,"seasons":["fall","winter","spring"],"material":"wool blend","style_tags":["classic","formal","preppy"]}` |
| `edge_shacket.jpg` | `{"type":"jacket","primary_color":"tan","secondary_color":null,"pattern":"solid","formality":2,"seasons":["fall","spring"],"material":"cotton","style_tags":["casual","trendy","classic"]}` |

**Improvements vs V3:**

- Examples target **recurring errors** (e.g. slip dress → top, long blazer → coat) instead of only “obvious” categories.
- Same V2 contract everywhere; **exceptions** are taught by **paired** images + labels.

**Trade-offs:**

- Requires ongoing curation: save failure images, align JSON with the actual garment, restart backend after changing examples.

---

## Summary: progression at a glance

| Iteration | Core idea | Prompt text vs previous | Main gain |
|-----------|-----------|---------------------------|-----------|
| **V1** | Long rules + heuristics | — | Explainable categories; strong written disambiguation |
| **V2** | Short zero-shot + schema + targets/hero | Replaced V1 prose with compact instruction | Maintainability; stable DB-shaped output |
| **V3** | V2 + generic multimodal few-shot | Same text as V2; added demo turns | Model sees valid image→JSON demonstrations |
| **V4** | V3 + hybrid edge examples | Same text as V2/V3; swap example set | Fixes project-specific confusions, not only generic SKUs |

**Note:** V3 and V4 differ only in **which** few-shot images and JSON strings you ship; the **instruction paragraph** stays the V2 block.

---

## Is V4 the “best” iteration — and why?

**For StyleSync’s goals (accurate tags that feed scoring, outfits, and recommendations), V4 is the strongest *design* in this sequence**, because it keeps everything that worked in V2–V3 and adds **targeted repair** for the mistakes your app actually sees.

**Why V4 is preferable to V1–V3**

| Compared to | Why V4 is stronger |
|---------------|-------------------|
| **V1** | V1’s long prose does not guarantee compliance; V4 still uses a **short, stable schema contract** (V2 text) and fixes gaps with **vision-grounded** examples instead of only more rules. |
| **V2** | Zero-shot is clean and cheap, but it cannot “show” the model what a **hard** case should look like; V4 adds those demonstrations only where needed. |
| **V3** | Generic few-shot helps format and generic categories; **hybrid** examples in V4 align demonstrations with **your** failure distribution (e.g. slip dress vs top), which is usually where accuracy gains matter most. |

**What “best” does *not* mean**

- **V4 is not automatically the highest accuracy on every photo** if example files are missing, mislabeled, or a poor match to the query (wrong angle, lighting, or garment class).
- **Best** here means **best trade-off for iterative improvement**: same prompt as V2, optional multimodal teaching, and **data-driven** example curation instead of endlessly lengthening V1-style rules.

**When V2 alone might be enough**

- Very constrained inputs (e.g. flat-lay catalog crops), or when you want minimum latency and no example maintenance — then a tight V2-style prompt without few-shot can be sufficient.

**Practical takeaway for the report**

- **V4 is the recommended iteration** for production-style wardrobe tagging in this project: **schema + rules in text (V2), plus failure-driven multimodal examples (V4)**. It is “best” relative to V1–V3 **for closing the gap between generic vision behavior and your app’s edge cases**, not because the prompt text alone is longer or more complex.

---

## HF → Groq: the pipeline we started with (and why Gemini came next)

### How we built the tagging stack in order

StyleSync **began** with the **Hugging Face → Groq** pipeline as the **default** wardrobe tagging path: it was a practical MVP—**caption the image** with a publicly available vision model on Hugging Face Inference, then **structure attributes** with Groq (fast JSON, good for a small schema). No multimodal Google key was required to get end-to-end uploads working.

**Later**, we added **Gemini vision** as a **second path**, exposed as **“Retag with Gemini”** (and optional multi-target retag). Gemini does **not** replace the old pipeline in all cases: the default upload flow still uses HF → Groq unless the user chooses Gemini retag; and when Gemini fails, code can **fall back** to HF → Groq so tagging still returns something usable.

So the story for your report is: **we started with HF → Groq; we moved *forward* by adding Gemini for higher-quality, vision-grounded tagging when it matters.**

### How the HF → Groq path works

1. **Image → caption (Hugging Face Inference API)**  
   - Model: `Salesforce/blip2-opt-2.7b-coco`  
   - The API receives **raw image bytes**; there is **no custom text prompt** to BLIP2 in code—only the image. Output is a **short natural-language caption**.

2. **Caption → JSON (Groq)**  
   - Model: `llama-3.3-70b-versatile`  
   - The **only** text prompt is `_groq_caption_to_json`: it injects the caption and asks for a single JSON object.

**Exact Groq prompt template (caption is interpolated):**

```
You are a fashion attribute extractor. Given a short description of a clothing item, output ONLY a single valid JSON object with these exact keys. No other text, no markdown, no code block.

Description: {caption}

Output exactly this structure (use null where not applicable):
{"type": "shirt|pants|dress|jacket|coat|shoes|skirt|sweater|blouse|t-shirt|etc", "primary_color": "specific color e.g. navy blue, beige", "secondary_color": null or a second color, "pattern": "solid|stripes|floral|geometric|plaid|etc", "formality": 1-5 (1=gym, 2=casual, 3=smart casual, 4=business, 5=formal), "seasons": ["spring","summer","fall","winter"], "material": "cotton|wool|silk|etc", "style_tags": ["minimal","classic","trendy", etc]}
```

- Settings: `temperature=0.1`, `max_tokens=400`  
- Flow: parse JSON → `_parse_and_validate`; **retry Groq once** on failure; else **default attributes**.

### How Gemini differs

| Aspect | HF → Groq | Gemini (retag / vision) |
|--------|-----------|-------------------------|
| **Sees the image?** | Only BLIP2 sees pixels; Groq sees **text only**. | One multimodal model sees **image + instructions** (and optional few-shot images). |
| **Information loss** | Caption may omit details (texture, fit, multi-item scenes). | Can use fine-grained visual cues directly. |
| **Schema** | Groq prompt schema is **shorter** and not identical to Gemini’s (e.g. `type` examples differ). | Aligns with app fields + targets / hero / optional `items` + V4 few-shot. |
| **Cost / deps** | HF token + Groq key. | `GEMINI_API_KEY` (+ optional example assets). |
| **Fallback** | Defaults if caption/JSON fails. | Gemini can **fall back** to the full HF → Groq pipeline (`recognize_clothing_gemini` → `recognize_clothing`). |

### Is Gemini “better” for StyleSync?

**Short answer:** *Often yes* for the photos that matter most to this app—**not** because Gemini is always “smarter,” but because the HF → Groq design **bakes in a hard bottleneck**: the caption.

1. **Errors are not locked in at the caption step**  
   In HF → Groq, every later decision (type, color, pattern, formality) is inferred from **one** short caption. If the caption is vague, wrong, or focused on the wrong object (e.g. “person in a room” instead of the skirt), Groq can only **harmonize** that text into JSON—it cannot recover pixels it never saw. Gemini **conditions structured output on the image directly**, so difficult photos—**busy scenes, multiple garments, subtle categories** (dress vs top, blazer vs coat)—are not collapsed into a single lossy sentence first.

2. **Why that matters downstream**  
   StyleSync uses these fields for **utility scoring**, **outfit matching**, and **shopping recommendations**. A systematic error at `type` or `primary_color` propagates. Reducing **caption-induced** mistakes is therefore high leverage; Gemini targets that failure mode.

3. **When HF → Groq is still the right tool**  
   It can be **fast**, **cheap**, and **good enough** for **simple, clear single-item** shots (flat lay, one obvious garment). It remains the **default upload** path and a **useful fallback**: if Gemini vision fails or returns unusable JSON, the implementation can still run **HF → Groq** so the user gets a tag instead of a hard failure.

4. **How we use both in practice**  
   Default tagging stays HF → Groq for breadth and simplicity; **Retag with Gemini** is the **quality upgrade** when users need accurate tags for messy real-world images. That matches “started with HF → Groq, then added Gemini” rather than replacing the entire stack overnight.

### What else you can try on the HF → Groq side

1. **Stronger / different caption model** on HF (if inference supports it) so Groq gets richer text.  
2. **Align Groq’s JSON schema** with Gemini’s (same `type` enum, same keys) so downstream logic behaves consistently whichever path ran.  
3. **Two-step Groq:** first ask for a **structured bullet list** of observations from the caption, then a second call to map that to JSON (sometimes reduces hallucination).  
4. **Few-shot in Groq:** 1–2 example caption → JSON pairs in the prompt (text-only few-shot).  
5. **Caption repair:** if caption is empty/generic, use Groq to expand “A clothing item.” with a generic template (weak) or require re-upload.  
6. **Ensemble:** run both pipelines and merge with rules (e.g. prefer Gemini for `type` if confidence heuristic differs).  

Implementation for (1)–(6) is **not** all in the repo today; the table describes **directions**, not shipped features.

# Translation manifest, version 1

Existing version-1 manifests remain usable. New fields are optional. Coordinates are source-page PDF points, on the Chinese half only. `prepare_manifest.py` writes a source hash and refuses to overwrite an existing manifest unless `--force` is supplied.

## Basic entries

```json
{
  "schema_version": 1,
  "document": {"source_name": "course.pdf", "output_title": "课程讲义 - 中文/法语对照版"},
  "word_replacements": [],
  "pages": [{
    "page": 1,
    "size": [595.276, 841.89],
    "blocks": [{
      "id": 3,
      "bbox": [70, 180, 525, 205],
      "source": "La fonction d'onde ...",
      "action": "translate",
      "translation": "波函数……",
      "font_size": 10,
      "color": "#000000"
    }],
    "groups": [], "overlays": [], "preserved_regions": []
  }]
}
```

- `translate`: requires a nonempty translation.
- `preserve`: retains source equations, variables, units or numbers.
- `ignore`: text handled elsewhere, a proper name or an empty block. Explain the reason for prose and provide its translation in the corresponding overlay/replacement. Position near a margin is insufficient.
- `bbox` records extraction; use `rect` to override placement/masking without altering block IDs.
- `review_flags` is a preparation hint, not permission to omit a page or proof of a defect.

## Groups and precise masks

Use a group to replace a coherent mixed sentence as one unit. Its `blocks` IDs are skipped individually; groups must not share IDs.

```json
{"blocks": [5, 6], "translation": "其中 dS 为面积元。", "font_size": 10}
```

Default masking uses the group union or block rectangle. When that would erase adjacent math, override the rectangles:

```json
{
  "blocks": [5, 6],
  "rect": [70, 180, 525, 215],
  "mask_rects": [[70, 180, 525, 191], [70, 192, 130, 204]],
  "text_rect": [70, 180, 525, 203],
  "translation": "由于两个函数的变量独立，各部分均满足归一化条件。"
}
```

- `mask_rects` is the exact list of rectangles erased, without additional padding.
- `text_rect` is the available Chinese text area, independent of the masks.
- Without explicit `text_rect`, the builder allows a small amount of available space below the source block for CJK font metrics, stopping before the next lower text block.
- Do not use a full-width mask for a short wrapped word beside an integral or a superscript. Original Word/TeX math may extend beyond its extracted bbox; inspect the actual source region.

## Overlays, erasing fragments and restored formulas

An overlay has the same formatting fields and a required `rect`. Use `id` for stable updates when moving a rectangle.

```json
{
  "id": "vertical-axis",
  "rect": [137, 107, 160, 271],
  "translation": "径向概率密度 R<sup>2</sup>(r)r<sup>2</sup>",
  "font_size": 11,
  "rotation": 90,
  "padding": [0, 0, 0, 0]
}
```

Clear a leftover wrapped French fragment already translated in another entry with an explicit eraser, rather than whitespace pretending to be a translation:

```json
{"id": "wrapped-tail", "rect": [82, 303, 140, 315], "erase_only": true,
 "reason": "Continuation translated in the preceding overlay", "padding": [0, 0, 0, 0]}
```

Page-level `preserved_regions` is a list of source clips pasted back at their exact coordinates. Use it for intact equations whose integral limits or exponents share a prose bbox:

```json
"preserved_regions": [[182, 308.6, 438, 340.2]]
```

The order is: prose masks → restored source clips → word-replacement masks → frame rules → all Chinese text. This prevents a later mask from wiping out Chinese already drawn. Restored clips should contain math, not prose; if they include a label such as `espace`, translate that label with a clipped word replacement afterward.

## Word replacements

`source` and `target` accept the literal placeholder `{page}`; other braces remain literal. `pages` is `"all"` or a list of one-based pages. Optional `clip` confines matching to a header or formula label, avoiding accidental replacements inside body text.

```json
{"source": "Thermodynamique", "target": "热力学", "pages": "all",
 "clip": [0, 0, 595, 45], "font_size": 9, "align": "center", "padding": [1, 0.3, 1, 0.5]}
```

## Typography and fonts

All translated entries accept:

| Field | Meaning |
|---|---|
| `font_size` | Source-scale starting size, no global title cap |
| `min_font_size` | Fit floor; defaults to 7 pt, or the starting size if smaller |
| `line_height` | Relative line height, default 1.12 |
| `color` / `background` | `#RRGGBB`; default black text / white mask |
| `align` | `left`, `center`, `right`, `justify` |
| `bold` | Boolean, for hierarchy/emphasis |
| `padding` | Mask expansion `[left, top, right, bottom]`, default `[0.5, 0.3, 0.5, 0.6]` |
| `rotation` | 0, 90, 180 or 270; explicit, independent of the label text |
| `rect`, `mask_rects`, `text_rect` | Geometry overrides described above |

Text is literal except the small allowlist `<sub> <sup> <b> <strong> <i> <em> <br>`. Literal comparisons such as `x < y` and other markup are escaped. Simple CJK text uses native text placement; tight text and rich/math text use a font-embedded HTML box. Missing CJK-font glyphs are explicitly assigned to the math font; a CSS fallback list alone is insufficient.

Default Chinese font is PyMuPDF's embedded Droid Sans Fallback. Math font discovery uses system Cambria or DejaVu Sans where available. Override fonts at the manifest top level when needed; paths are absolute or relative to the manifest:

```json
"fonts": {"cjk": "fonts/chinese.ttf", "math": "fonts/math.ttf"}
```

Unsupported glyphs fail before building. Prefer source equation artwork for complicated vectors, radicals and matrices. Do not silently replace unusual symbols with different physical notation.

## Compact updates and repeatable repairs

```json
{
  "source_translations": {"Définitions": "定义"},
  "blocks": {
    "1:3": "波函数……",
    "1:4": {"action": "preserve", "reason": "Standalone equation"},
    "1:8": {"text_rect": [70, 180, 525, 210], "font_size": 10}
  },
  "groups": [{"page": 1, "blocks": [12, 13], "translation": "其中……"}],
  "overlays": [{"page": 1, "id": "axis", "rect": [137, 107, 160, 271], "translation": "径向密度", "rotation": 90}],
  "page_updates": {"1": {"preserved_regions": [[182, 308.6, 438, 340.2]]}},
  "document": {"output_title": "课程讲义 - 中文/法语对照版"}
}
```

Run `python scripts/apply_translations.py translations.json updates.json`. Strings in `blocks` mean `action: translate`. Exact `source_translations` apply first; page:block overrides take precedence. Groups and overlays are **upserted**, not blindly appended: identity is `id` when supplied, otherwise the group ID set or overlay rectangle. Moving an overlay without an `id` creates a distinct entry, so assign IDs to anticipated repairs. Existing unrelated entries remain unchanged. `word_replacements`, if provided, replaces that entire list.

## Preview and verification options

`--pages auto` selects first, last, a dense page and complex pages. `--pages 1,3-5` selects explicit pages; `--pages all` renders all; `--pages none` skips full-size page previews but still permits overview sheets. `verify_dual_pdf.py --full` compares every French page and renders all pages when `--render-dir` is supplied. Without a render directory it only runs deterministic checks.

Build reports include output/manifest/source hashes, page content keys and actual font sizes. Preview caches use those keys plus DPI; unchanged pages and unchanged overview sheets are reused. Quick checks do not certify translation accuracy or inspect raster image labels. Review the selected images and risk areas once, then repair only pages affected by a finding.

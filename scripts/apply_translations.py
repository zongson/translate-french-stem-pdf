#!/usr/bin/env python3
"""Apply compact page:block translation updates to a generated manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ALLOWED_BLOCK_FIELDS = {
    "action", "translation", "reason", "font_size", "color", "align", "padding", "line_height",
    "rect", "text_rect", "mask_rects", "min_font_size", "rotation", "bold", "background"
}


def parse_key(key: str) -> tuple[int, int]:
    try:
        page, block = key.split(":", 1)
        return int(page), int(block)
    except Exception as exc:
        raise ValueError(f"Invalid block key {key!r}; expected 'page:block'") from exc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest_json", type=Path)
    parser.add_argument("updates_json", type=Path)
    parser.add_argument("--output", type=Path, help="Write a new manifest instead of updating in place")
    args = parser.parse_args()

    manifest = json.loads(args.manifest_json.read_text(encoding="utf-8"))
    updates = json.loads(args.updates_json.read_text(encoding="utf-8"))
    pages = {int(page["page"]): page for page in manifest.get("pages", [])}
    blocks = {
        (pno, int(block["id"])): block
        for pno, page in pages.items()
        for block in page.get("blocks", [])
    }

    # Apply a repeated exact source phrase once, with block-specific updates below
    # taking precedence. This is translation reuse, not an automatic translator.
    for source, translation in updates.get("source_translations", {}).items():
        for block in blocks.values():
            if block.get("source") == source:
                block.update(action="translate", translation=translation, reason="")

    for key, value in updates.get("blocks", {}).items():
        identity = parse_key(key)
        if identity not in blocks:
            raise ValueError(f"Unknown block {key}")
        block = blocks[identity]
        if isinstance(value, str):
            block["action"] = "translate"
            block["translation"] = value
            block["reason"] = ""
        elif isinstance(value, dict):
            unknown = set(value) - ALLOWED_BLOCK_FIELDS
            if unknown:
                raise ValueError(f"Block {key} has unsupported fields: {sorted(unknown)}")
            block.update(value)
        else:
            raise ValueError(f"Block {key} update must be a string or object")

    for collection in ("groups", "overlays"):
        for item in updates.get(collection, []):
            if "page" not in item:
                raise ValueError(f"{collection} update is missing page")
            pno = int(item["page"])
            if pno not in pages:
                raise ValueError(f"Unknown page {pno} in {collection}")
            value = dict(item)
            value.pop("page")
            existing = pages[pno].setdefault(collection, [])
            def identity(item):
                if item.get("id") is not None:
                    return ("id", item["id"])
                return tuple(sorted(item["blocks"])) if collection == "groups" else tuple(item["rect"])
            key = identity(value)
            # Reapplying the same updates replaces the entry instead of stacking
            # white masks and duplicate text. It also collapses older duplicates.
            matches = [i for i, entry in enumerate(existing) if identity(entry) == key]
            if matches:
                existing[matches[0]] = value
                for i in reversed(matches[1:]):
                    del existing[i]
            else:
                existing.append(value)

    for pno, fields in updates.get("page_updates", {}).items():
        if int(pno) not in pages:
            raise ValueError(f"Unknown page {pno}")
        unknown = set(fields) - {"preserved_regions", "review_flags"}
        if unknown:
            raise ValueError(f"Unsupported page fields: {sorted(unknown)}")
        pages[int(pno)].update(fields)

    for key in ("document", "fonts"):
        if key in updates:
            manifest.setdefault(key, {}).update(updates[key])

    if "word_replacements" in updates:
        if not isinstance(updates["word_replacements"], list):
            raise ValueError("word_replacements must be a list")
        manifest["word_replacements"] = updates["word_replacements"]

    destination = args.output or args.manifest_json
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()


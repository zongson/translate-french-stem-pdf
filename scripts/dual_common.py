"""Shared manifest, font and preview helpers. Requires PyMuPDF and Pillow."""
from __future__ import annotations

import hashlib
import html
import json
import os
from pathlib import Path
import re
import tempfile

import pymupdf as fitz

DEFAULT_PADDING = [0.5, 0.3, 0.5, 0.6]
FORMULA_WORDS = {'sin', 'cos', 'tan', 'exp', 'log', 'ln', 'lim', 'max', 'min', 'det', 'grad', 'div', 'rot', 'sqrt', 'vec'}
PROSE_WORDS = {'et', 'en', 'de', 'le', 'la', 'les', 'un', 'une', 'est', 'avec', 'soit', 'donc', 'où', 'ou', 'à', 'on', 'si', 'sur', 'pour', 'dans', 'remarque', 'exemple'}
TAG = re.compile(r'(<(?:/?(?:sub|sup|b|strong|i|em)|br\s*/?)>)', re.I)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


def file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def plain_text(text):
    return html.unescape(TAG.sub('', text or ''))


def block_text(block):
    return '\n'.join(''.join(s.get('text', '') for s in l.get('spans', [])) for l in block.get('lines', [])).strip()


def looks_like_prose(text):
    words = re.findall(r'[^\W\d_]+', text.lower(), re.UNICODE)
    return bool(set(words) & PROSE_WORDS) or any(len(w) >= 3 and w not in FORMULA_WORDS for w in words)


def cjk_count(text):
    return sum('\u3400' <= c <= '\u9fff' for c in text)


def expand(rect, padding=None):
    left, top, right, bottom = DEFAULT_PADDING if padding is None else padding
    r = fitz.Rect(rect)
    return fitz.Rect(r.x0-left, r.y0-top, r.x1+right, r.y1+bottom)


def selected_pages(spec, page_number):
    return spec == 'all' or page_number in spec


def manifest_checks(manifest):
    errors, warnings = [], []
    if manifest.get('schema_version') != 1:
        errors.append('Unsupported schema_version')
    page_numbers = [p.get('page') for p in manifest.get('pages', [])]
    if len(set(page_numbers)) != len(page_numbers):
        errors.append('Duplicate page numbers')
    for page in manifest.get('pages', []):
        pno = page.get('page')
        ids = [b['id'] for b in page.get('blocks', [])]
        if len(set(ids)) != len(ids):
            errors.append(f'Page {pno}: duplicate block IDs')
        grouped = set()
        for b in page.get('blocks', []):
            if b.get('action') not in ('translate','preserve','ignore'):
                errors.append(f'Page {pno} block {b["id"]}: invalid action {b.get("action")}')
        for g in page.get('groups', []):
            bids = g.get('blocks', [])
            if not bids or len(bids) != len(set(bids)) or any(i < 0 or i not in ids for i in bids):
                errors.append(f'Page {pno}: invalid group IDs {bids}')
            if grouped.intersection(bids):
                errors.append(f'Page {pno}: a block occurs in multiple groups')
            grouped.update(bids)
        for collection in ('blocks', 'groups', 'overlays'):
            for index, item in enumerate(page.get(collection, [])):
                if collection == 'blocks' and (item['id'] in grouped or item.get('action') != 'translate'):
                    if item['id'] not in grouped and item.get('action') in ('preserve', 'ignore') and looks_like_prose(item.get('source', '')):
                        if not item.get('reason'):
                            warnings.append(f'Page {pno} block {item["id"]}: untranslated prose needs a reason')
                    continue
                if item.get('erase_only'):
                    if not item.get('reason'):
                        errors.append(f'Page {pno} {collection} {index}: erase_only needs a reason')
                elif not plain_text(item.get('translation')).strip():
                    if collection == 'overlays' and item.get('translation'):
                        warnings.append(f'Page {pno} overlay {index}: legacy whitespace mask; prefer erase_only with a reason')
                    else:
                        errors.append(f'Page {pno} {collection} {index}: missing translation')
                if item.get('rotation', 0) not in (0, 90, 180, 270):
                    errors.append(f'Page {pno} {collection} {index}: rotation must be 0/90/180/270')
    for item in manifest.get('word_replacements', []):
        if not item.get('source') or not plain_text(item.get('target')).strip():
            errors.append('Word replacement requires source and target')
    return errors, warnings


def translation_texts(manifest):
    for item in manifest.get('word_replacements', []):
        yield item.get('target', '')
    for page in manifest.get('pages', []):
        grouped = {i for g in page.get('groups', []) for i in g['blocks']}
        for b in page.get('blocks', []):
            if b.get('action') == 'translate' and b['id'] not in grouped:
                yield b.get('translation', '')
        for key in ('groups', 'overlays'):
            for item in page.get(key, []):
                if not item.get('erase_only'):
                    yield item.get('translation', '')


class Fonts:
    """Embed a CJK font and explicitly route missing math glyphs to a math font."""
    def __init__(self, config=None, base=None):
        config = config or {}
        def configured(key):
            p = Path(config[key]).expanduser()
            return p if p.is_absolute() else Path(base or '.') / p
        self.cjk = fitz.Font(fontfile=str(configured('cjk'))) if config.get('cjk') else fitz.Font(fontname='china-s')
        self.math = None
        if config.get('math'):
            self.math = fitz.Font(fontfile=str(configured('math')))
        else:
            candidates = [Path(os.environ.get('WINDIR', 'C:/Windows'))/'Fonts/cambria.ttc',
                          Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
                          Path('/Library/Fonts/Arial Unicode.ttf')]
            for path in candidates:
                if path.is_file():
                    self.math = fitz.Font(fontfile=str(path))
                    break
        self._tmp = None
        self._archive = None

    def missing(self, text):
        return sorted({c for c in plain_text(text) if not c.isspace() and not self.cjk.has_glyph(ord(c))
                       and not (self.math and self.math.has_glyph(ord(c)))})

    @property
    def archive(self):
        if self._archive is None:
            self._tmp = tempfile.TemporaryDirectory(prefix='dual-fonts-')
            root = Path(self._tmp.name)
            (root/'cjk.ttf').write_bytes(self.cjk.buffer)
            if self.math:
                (root/'math.ttf').write_bytes(self.math.buffer)
            self._archive = fitz.Archive(str(root))
        return self._archive

    def rich(self, text):
        def escape_run(run):
            # CSS fallback lists alone can leave blank glyphs in MuPDF Story.
            parts, current, math_run = [], [], None
            for c in run:
                use_math = not c.isspace() and not self.cjk.has_glyph(ord(c))
                if math_run is not None and math_run != use_math:
                    s = html.escape(''.join(current))
                    parts.append(f'<span style="font-family:DualMath">{s}</span>' if math_run else s)
                    current = []
                current.append(c)
                math_run = use_math
            if current:
                s = html.escape(''.join(current))
                parts.append(f'<span style="font-family:DualMath">{s}</span>' if math_run else s)
            return ''.join(parts).replace('\n', '<br>')
        return ''.join(p if TAG.fullmatch(p) else escape_run(p) for p in TAG.split(text))

    def close(self):
        self._archive = None
        if self._tmp:
            self._tmp.cleanup()


def choose_pages(spec, count, page_specs=None):
    if spec == 'none' or count == 0:
        return []
    if spec == 'all':
        return list(range(1, count+1))
    if spec == 'auto':
        pages = page_specs or []
        dense = max(pages, key=lambda p: sum(len(b.get('source', '')) for b in p.get('blocks', [])), default={'page':1})['page']
        ranked = sorted(pages, key=lambda p: len(p.get('review_flags', []))*3 + len(p.get('groups', [])) + len(p.get('overlays', [])), reverse=True)
        return sorted({1, count, dense, *[p['page'] for p in ranked[:2]]})
    chosen = set()
    for segment in spec.split(','):
        endpoints = segment.strip().split('-')
        a, b = (int(endpoints[0]), int(endpoints[-1]))
        chosen.update(range(a, b+1))
    if not chosen or min(chosen) < 1 or max(chosen) > count:
        raise ValueError(f'Page selection outside 1..{count}: {spec}')
    return sorted(chosen)


def render_previews(doc, folder, pages, keys, dpi=110, overview=True):
    """Cache page previews by content key; contact sheets use small independent renders."""
    from PIL import Image, ImageDraw
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    index_path = folder/'preview-index.json'
    index = read_json(index_path) if index_path.exists() else {}
    paths, rendered = [], []
    for number in pages:
        key = digest([keys[number-1], dpi])
        path = folder/f'page-{number:03d}.png'
        if index.get(str(number)) != key or not path.exists():
            doc[number-1].get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72), alpha=False).save(path)
            index[str(number)] = key
            rendered.append(number)
        paths.append(str(path))
    sheets = []
    if overview:
        cols, per_sheet, thumb_w = 2, 6, 420
        thumb_h = max(round(thumb_w*p.rect.height/p.rect.width) for p in doc)
        for start in range(0, len(doc), per_sheet):
            path = folder/f'overview-{start//per_sheet+1:02d}.png'
            overview_key = digest(keys[start:start+per_sheet])
            overview_id = f'overview-{start//per_sheet+1:02d}'
            if index.get(overview_id) != overview_key or not path.exists():
                sheet = Image.new('RGB', (cols*(thumb_w+16), 3*(thumb_h+32)), 'white')
                draw = ImageDraw.Draw(sheet)
                for offset in range(min(per_sheet, len(doc)-start)):
                    page = doc[start+offset]
                    pix = page.get_pixmap(matrix=fitz.Matrix(thumb_w/page.rect.width, thumb_w/page.rect.width), alpha=False)
                    im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
                    x, y = (offset%cols)*(thumb_w+16)+8, (offset//cols)*(thumb_h+32)+24
                    sheet.paste(im, (x,y))
                    draw.text((x,y-18), f'Page {start+offset+1}', fill='black')
                sheet.save(path)
            index[overview_id] = overview_key
            sheets.append(str(path))
    write_json(index_path, index)
    return {'selected_pages': pages, 'newly_rendered_pages': rendered, 'page_previews': paths, 'overviews': sheets}

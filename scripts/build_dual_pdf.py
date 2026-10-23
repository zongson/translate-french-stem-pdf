#!/usr/bin/env python3
"""Build a source-scale Chinese-left/French-right PDF from a version-1 manifest."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import tempfile
import time

import pymupdf as fitz

from dual_common import (Fonts, TAG, digest, expand, file_digest, manifest_checks,
                         plain_text, read_json, selected_pages, translation_texts, write_json)

ALIGN = {'left':0, 'center':1, 'right':2, 'justify':3}


def rgb(value, fallback=(0,0,0)):
    if value is None:
        return fallback
    if isinstance(value, (list,tuple)) and len(value) == 3:
        return tuple(value)
    value = value.lstrip('#')
    if len(value) != 6:
        raise ValueError(f'Invalid color {value!r}')
    return tuple(int(value[i:i+2],16)/255 for i in (0,2,4))


def rectangle(value, bounds, label):
    r = fitz.Rect(value)
    if r.is_empty or r.is_infinite or not all(abs(n) < 1e7 for n in r):
        raise ValueError(f'{label}: invalid rectangle {value}')
    # Never let a Chinese-side overlay enter the French copy.
    r &= bounds
    if r.is_empty:
        raise ValueError(f'{label}: rectangle lies outside source page')
    return r


def collect_operations(src_page, spec, replacements):
    blocks = [b for b in src_page.get_text('dict')['blocks'] if b.get('type') == 0]
    entries = {b['id']:b for b in spec.get('blocks', [])}
    operations, grouped = [], set()

    def add(item, rect, label, defaults=None, after_restore=False):
        op = dict(defaults or {})
        op.update(item)
        op['label'] = label
        op['rect'] = list(rect)
        op['after_restore'] = after_restore
        op['mask_rects'] = [list(rectangle(r,src_page.rect,label)) for r in op.get('mask_rects', [expand(rect,op.get('padding'))])]
        text_rect = expand(rect,op.get('padding'))
        if 'text_rect' not in op and not op.get('rotation'):
            # Use only available inter-block whitespace for CJK font metrics.
            next_y = min((b['bbox'][1] for b in blocks if b['bbox'][1] >= text_rect.y1
                          and b['bbox'][0] < text_rect.x1 and b['bbox'][2] > text_rect.x0),
                         default=src_page.rect.height)
            text_rect.y1 = min(text_rect.y1+op.get('font_size',10)*.5,max(text_rect.y1,next_y-.4))
        op['text_rect'] = list(rectangle(op.get('text_rect',text_rect),src_page.rect,label))
        operations.append(op)

    for g in spec.get('groups', []):
        ids = g['blocks']
        if any(i < 0 or i >= len(blocks) for i in ids):
            raise ValueError(f'Page {spec["page"]}: invalid group {ids}')
        grouped.update(ids)
        union = fitz.Rect(blocks[ids[0]]['bbox'])
        for i in ids[1:]:
            union.include_rect(blocks[i]['bbox'])
        add(g,g.get('rect',union),f'group {ids}',entries.get(ids[0]))
    for bid,b in entries.items():
        if bid < 0 or bid >= len(blocks):
            raise ValueError(f'Page {spec["page"]}: invalid block {bid}')
        if bid not in grouped and b.get('action') == 'translate':
            add(b,b.get('rect',blocks[bid]['bbox']),f'block {bid}')
    for i,ov in enumerate(spec.get('overlays', [])):
        add(ov,ov['rect'],f'overlay {ov.get("id",i)}')
    for item in replacements:
        if not selected_pages(item.get('pages','all'),spec['page']):
            continue
        text = item['source'].replace('{page}',str(spec['page']))
        clip = fitz.Rect(item['clip']) if item.get('clip') else None
        for index,found in enumerate(src_page.search_for(text,clip=clip)):
            op = dict(item,translation=item['target'].replace('{page}',str(spec['page'])))
            add(op,found,f'word {text!r} #{index}',after_restore=True)
    return operations


def place(page, op, fonts):
    text = op['translation']
    r = fitz.Rect(op['text_rect'])
    size = float(op.get('font_size',10))
    minimum = min(size,float(op.get('min_font_size',7)))
    if size <= 0 or minimum <= 0:
        raise ValueError(f'{op["label"]}: font sizes must be positive')
    color = rgb(op.get('color'))
    rotation = op.get('rotation',0)
    line_height = float(op.get('line_height',1.12))
    missing = fonts.missing(text)
    if missing:
        raise ValueError(f'{op["label"]}: unsupported glyphs {missing}; preserve source math or configure fonts.math')
    rich = bool(TAG.search(text)) or bool(op.get('bold')) or any(not c.isspace() and not fonts.cjk.has_glyph(ord(c)) for c in text)
    if not rich:
        page.insert_font(fontname='DualCJK',fontbuffer=fonts.cjk.buffer)
        shape = page.new_shape()
        spare = shape.insert_textbox(r,text,fontsize=size,fontname='DualCJK',color=color,
                                    align=ALIGN.get(op.get('align','left'),0),lineheight=line_height,rotate=rotation)
        if spare >= -0.01:
            shape.commit()
            return size,'native'
        # Story often fits source-scale Chinese better in tight one-line boxes.
    color_hex = '#'+''.join(f'{round(c*255):02x}' for c in color)
    css = ("@font-face{font-family:DualCJK;src:url(cjk.ttf);}"
           "@font-face{font-family:DualMath;src:url(math.ttf);}"
           "*{margin:0;padding:0;}"
           f"body{{font-family:DualCJK;font-size:{size}pt;line-height:{line_height};color:{color_hex};"
           f"text-align:{op.get('align','left')};font-weight:{'bold' if op.get('bold') else 'normal'};}}"
           "sub,sup{font-size:72%;}")
    spare,scale = page.insert_htmlbox(r,fonts.rich(text),css=css,archive=fonts.archive,
                                     rotate=rotation,scale_low=minimum/size)
    if spare < 0:
        raise ValueError(f'{op["label"]}: translation does not fit at {minimum:g} pt; shorten prose or set text_rect/min_font_size')
    return size*scale,'rich'


def redraw_long_rules(out_page, src_page, masks=None):
    """Restore touched page/frame rules, not short equation bars."""
    for path in src_page.get_drawings():
        for item in path.get('items', []):
            if item[0] != 're':
                continue
            r = fitz.Rect(item[1])
            horizontal = r.height <= 3.1 and r.width >= src_page.rect.width*.5
            vertical = r.width <= 1.05 and r.height >= 5 and (r.x0 < 80 or r.x0 > src_page.rect.width-80)
            if (horizontal or vertical) and (masks is None or any((r+(-1,-1,1,1)).intersects(m) for m in masks)):
                out_page.draw_rect(r,color=path.get('color'),fill=path.get('fill'),width=path.get('width') or .5)


def build(source_path, manifest_path, output_path, allow_incomplete=False):
    started = time.perf_counter()
    source_path,manifest_path,output_path = map(Path,(source_path,manifest_path,output_path))
    if source_path.resolve() == output_path.resolve():
        raise ValueError('Output must not overwrite the French source')
    manifest = read_json(manifest_path)
    errors,warnings = manifest_checks(manifest)
    blocking = [e for e in errors if not allow_incomplete or 'missing translation' not in e]
    if blocking:
        raise ValueError('\n'.join(blocking))
    source_hash = file_digest(source_path)
    expected = manifest.get('document',{}).get('source_sha256')
    if expected and expected != source_hash:
        raise ValueError('Source PDF changed since preparation; prepare a new manifest')
    fonts = Fonts(manifest.get('fonts'),manifest_path.parent)
    missing = sorted({c for text in translation_texts(manifest) for c in fonts.missing(text)})
    if missing:
        fonts.close()
        raise ValueError(f'Unsupported translation glyphs: {missing}; configure fonts.math/cjk or preserve source notation')
    source,out = fitz.open(source_path),fitz.open()
    specs = {p['page']:p for p in manifest['pages']}
    if set(specs) != set(range(1,len(source)+1)):
        raise ValueError('Manifest pages do not match source PDF')
    placements,page_keys = [],[]
    font_key = [hashlib.sha256(f.buffer).hexdigest() for f in (fonts.cjk,fonts.math) if f]
    engine_key = [file_digest(Path(__file__)),file_digest(Path(__file__).with_name('dual_common.py'))]
    try:
        for pno,src in enumerate(source,start=1):
            spec = specs[pno]
            ops = collect_operations(src,spec,manifest.get('word_replacements',[]))
            w,h = src.rect.width,src.rect.height
            page = out.new_page(width=2*w,height=h)
            if src.get_contents():
                page.show_pdf_page(fitz.Rect(0,0,w,h),source,pno-1)
                page.show_pdf_page(fitz.Rect(w,0,2*w,h),source,pno-1)
            for after in (False,True):
                if after:
                    for region in spec.get('preserved_regions',[]):
                        r = rectangle(region,src.rect,'preserved_region')
                        page.draw_rect(r,color=None,fill=(1,1,1))
                        page.show_pdf_page(r,source,pno-1,clip=r,keep_proportion=False)
                for op in ops:
                    if op['after_restore'] == after:
                        for rect in op['mask_rects']:
                            page.draw_rect(rect,color=None,fill=rgb(op.get('background','#FFFFFF')))
            redraw_long_rules(page,src,[fitz.Rect(r) for op in ops for r in op['mask_rects']])
            for op in ops:
                if op.get('erase_only') or not plain_text(op.get('translation')).strip():
                    continue
                size,renderer = place(page,op,fonts)
                requested = op.get('font_size',10)
                placements.append({'page':pno,'label':op['label'],'font_size':round(size,2),
                                   'requested_size':requested,'renderer':renderer,'text_rect':op['text_rect']})
                if size < min(8,requested) or size < requested*.82:
                    warnings.append(f'Page {pno} {op["label"]}: small type {size:.1f} pt; inspect this region')
            page.draw_line((w-.6,18),(w-.6,h-18),color=(.75,.75,.75),width=.4)
            active_words = [item for item in manifest.get('word_replacements',[]) if selected_pages(item.get('pages','all'),pno)]
            page_keys.append(digest([source_hash,pno,spec,active_words,engine_key,font_key]))
        meta = dict(source.metadata or {})
        meta.update(title=manifest.get('document',{}).get('output_title',source_path.stem+' - 中文/法语对照版'),
                    subject='中文在左，法语原文在右',creator='translate-french-stem-pdf',producer='PyMuPDF')
        out.set_metadata(meta)
        out.subset_fonts()
        output_path.parent.mkdir(parents=True,exist_ok=True)
        fd,tmp_name = tempfile.mkstemp(suffix='.pdf',prefix='.dual-',dir=output_path.parent)
        os.close(fd)
        tmp = Path(tmp_name)
        try:
            out.save(tmp,garbage=4,deflate=True)
            tmp.replace(output_path)
        finally:
            tmp.unlink(missing_ok=True)
    finally:
        source.close()
        out.close()
        fonts.close()
    report = {'output':str(output_path.resolve()),'output_sha256':file_digest(output_path),'source_sha256':source_hash,
              'manifest_sha256':file_digest(manifest_path),
              'pages':len(specs),'page_keys':page_keys,'placements':placements,'warnings':warnings,
              'unsupported_glyphs':missing,'build_seconds':round(time.perf_counter()-started,3)}
    write_json(output_path.with_suffix('.build.json'),report)
    print(f'Built {len(specs)} pages in {report["build_seconds"]}s: {output_path}')
    if warnings:
        print(f'{len(warnings)} review notes in {output_path.with_suffix(".build.json")}')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input_pdf',type=Path)
    parser.add_argument('manifest_json',type=Path)
    parser.add_argument('output_pdf',type=Path)
    parser.add_argument('--allow-incomplete',action='store_true',help='Draft only; retains unfinished source blocks')
    args = parser.parse_args()
    build(args.input_pdf,args.manifest_json,args.output_pdf,args.allow_incomplete)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Extract a manifest, compact translation queue and optional cached source previews."""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import re

import pymupdf as fitz

from dual_common import (block_text, choose_pages, digest, file_digest, looks_like_prose,
                         render_previews, write_json)

COMMON_LABELS = {'Thermodynamique':'热力学','Physique':'物理','Chimie':'化学','Chimie quantique':'量子化学',
                 'Mathématiques':'数学','Mathematiques':'数学'}


def classify(text, block=None, page_height=None):
    # Top-of-page prose is still prose: position alone never means ignore.
    if not text:
        return 'ignore','Empty block'
    if not looks_like_prose(text):
        return 'preserve','Mathematical notation, numerical value or variable label'
    return 'translate',''


def prepare(input_pdf, output_json, force=False, render_dir=None, pages='auto'):
    input_pdf,output_json = Path(input_pdf),Path(output_json)
    if output_json.exists() and not force:
        raise ValueError(f'{output_json} exists; use updates to keep translations, or --force to reset it')
    source_hash = file_digest(input_pdf)
    doc = fitz.open(input_pdf)
    specs,replacements,queue = [],[],[]
    try:
        for pno,page in enumerate(doc,start=1):
            blocks = [b for b in page.get_text('dict')['blocks'] if b.get('type') == 0]
            entries,flags = [],set()
            if page.get_images():
                flags.add('raster_images: inspect embedded diagram labels')
            if len(page.get_text().strip()) < 30:
                flags.add('sparse_text: scan, blank page or image-based content')
            for bid,block in enumerate(blocks):
                text = block_text(block)
                spans = [s for line in block['lines'] for s in line['spans'] if s['text'].strip()]
                weights = Counter()
                colors = Counter()
                for span in spans:
                    weight = len(span['text'].strip())
                    weights[round(span['size'],2)] += weight
                    colors[span.get('color',0)] += weight
                size = weights.most_common(1)[0][0] if weights else 10
                color = colors.most_common(1)[0][0] if colors else 0
                action,reason = classify(text,block,page.rect.height)
                entry = {'id':bid,'bbox':[round(x,3) for x in block['bbox']], 'source':text,
                         'action':action,'translation':None,'font_size':size,'color':f'#{color&0xFFFFFF:06X}',
                         'align':'left','reason':reason}
                total = sum(len(s['text']) for s in spans)
                if total and sum(len(s['text']) for s in spans if s.get('flags',0)&16) > total*.65:
                    entry['bold'] = True
                # Automatic labels are exact full lines confined to the page margin.
                lines = [block_text({'lines':[line]}) for line in block['lines']]
                handled = []
                for line,raw in zip(block['lines'],lines):
                    y0,y1 = line['bbox'][1],line['bbox'][3]
                    margin = y1 < 45 or y0 > page.rect.height-35
                    target = COMMON_LABELS.get(raw)
                    if margin and re.fullmatch(r'Page\s+\d+',raw):
                        target = f'第 {pno} 页'
                    if margin and target:
                        replacements.append({'source':raw,'target':target,'pages':[pno],
                                             'clip':[0,max(0,y0-2),page.rect.width,min(page.rect.height,y1+2)],
                                             'font_size':size,'align':'left','padding':[.4,.2,.4,.4]})
                        handled.append(raw)
                if lines and all(raw in handled or not re.search('[A-Za-zÀ-ÿ]',raw) for raw in lines):
                    if handled:
                        entry.update(action='ignore',reason='Margin label translated by word_replacements')
                if action == 'translate' and any('Math' in s.get('font','') or s.get('font') in ('Symbol','MT Extra') for s in spans):
                    flags.add('mixed_prose_math: keep display equations or split masks')
                r = fitz.Rect(block['bbox'])
                if any(r.intersects(fitz.Rect(other['bbox'])) and (r & fitz.Rect(other['bbox'])).get_area() > 3
                       for other in blocks[bid+1:]):
                    flags.add('overlapping_text_boxes: use precise masks near formulas')
                entries.append(entry)
                display = text.translate(str.maketrans({'\x16':'—','\x1b':'ff','\x1c':'fi','\x1d':'fl','\x1e':'ffi'}))
                queue.append(f'{pno}:{bid} [{entry["action"]}] {display}\n')
            specs.append({'page':pno,'size':[round(page.rect.width,3),round(page.rect.height,3)],
                          'review_flags':sorted(flags),'blocks':entries,'groups':[],'overlays':[]})
        manifest = {'schema_version':1,'document':{'source_name':input_pdf.name,'source_sha256':source_hash,
                    'output_title':input_pdf.stem+' - 中文/法语对照版','subject':'中文在左，法语原文在右'},
                    'word_replacements':replacements,'pages':specs}
        write_json(output_json,manifest)
        queue_path = output_json.with_suffix('.queue.txt')
        queue_path.write_text('\n'.join(queue),encoding='utf-8')
        preview = None
        if render_dir:
            preview = render_previews(doc,render_dir,choose_pages(pages,len(doc),specs),
                                      [digest([source_hash,p['page']]) for p in specs])
        print(f'Prepared {len(doc)} pages: {output_json}\nTranslation queue: {queue_path}')
        if preview:
            print(f'Source previews: {preview["selected_pages"]}; overviews: {preview["overviews"]}')
        return manifest
    finally:
        doc.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('input_pdf',type=Path)
    p.add_argument('output_json',type=Path)
    p.add_argument('--force',action='store_true',help='Reset an existing manifest, discarding translations')
    p.add_argument('--render-dir',type=Path)
    p.add_argument('--pages',default='auto',help='auto, all, none or a list such as 1,3-5')
    a = p.parse_args()
    prepare(a.input_pdf,a.output_json,a.force,a.render_dir,a.pages)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Run cheap whole-document checks and cache selected previews; --full checks every page."""
from __future__ import annotations

import argparse
from pathlib import Path
import statistics
import time
import re

import pymupdf as fitz

from dual_common import (Fonts, choose_pages, cjk_count, digest, file_digest, manifest_checks,
                         read_json, render_previews, translation_texts, write_json)


def embedded_cjk_font(doc, characters):
    seen,largest,found = set(),0,False
    def normalized(name):
        return re.sub(r'[^\w]','',name.split('+')[-1]).lower()
    names = {normalized(s.get('font','')) for page in doc
             for b in page.get_text('dict')['blocks'] if b.get('type') == 0
             for line in b['lines'] for s in line['spans'] if cjk_count(s['text'])}
    for page in doc:
        for font in page.get_fonts(full=True):
            xref = font[0]
            if xref <= 0 or xref in seen:
                continue
            seen.add(xref)
            try:
                name,_,_,content = doc.extract_font(xref)
                largest = max(largest,len(content))
                if content:
                    # Subsetting can remove the font's Unicode cmap while the PDF
                    # ToUnicode map remains valid. Match actual Chinese spans to
                    # an embedded program instead of imposing a size/cmap guess.
                    base = normalized(name)
                    found |= len(base)>3 and any(len(n)>3 and (base.startswith(n) or n.startswith(base)) for n in names)
            except (ValueError,RuntimeError):
                continue
    return found,largest


def right_half_difference(source, dual, numbers):
    # Align crop origins before rasterizing. Comparing a clip starting at a
    # fractional A4 width falsely reports antialiasing shifts in untouched text.
    from PIL import Image, ImageChops, ImageStat
    results = {}
    for number in numbers:
        src,page = source[number-1],dual[number-1]
        w,h = src.rect.width,src.rect.height
        crop = page.cropbox
        try:
            page.set_cropbox(fitz.Rect(w,0,2*w,h))
            a,b = src.get_pixmap(alpha=False),page.get_pixmap(alpha=False)
            if (a.width,a.height) != (b.width,b.height):
                results[str(number)] = 255.0
                continue
            ia = Image.frombytes('RGB',(a.width,a.height),a.samples)
            ib = Image.frombytes('RGB',(b.width,b.height),b.samples)
            # Older outputs drew the separator on the boundary itself.
            region = (1,0,a.width,a.height)
            diff = ImageChops.difference(ia.crop(region),ib.crop(region))
            results[str(number)] = statistics.mean(ImageStat.Stat(diff).mean)
        finally:
            page.set_cropbox(crop)
    return results


def verify(source_pdf,manifest_json,dual_pdf,render_dir=None,pages='auto',full=False,report_path=None,min_cjk=20):
    started = time.perf_counter()
    manifest_json,dual_pdf = Path(manifest_json),Path(dual_pdf)
    manifest = read_json(manifest_json)
    errors,warnings = manifest_checks(manifest)
    fonts = Fonts(manifest.get('fonts'),manifest_json.parent)
    try:
        missing = sorted({c for text in translation_texts(manifest) for c in fonts.missing(text)})
    finally:
        fonts.close()
    if missing:
        errors.append(f'Unsupported translation glyphs: {missing}')
    source,dual = fitz.open(source_pdf),fitz.open(dual_pdf)
    try:
        output_hash = file_digest(dual_pdf)
        build_path = dual_pdf.with_suffix('.build.json')
        build = read_json(build_path) if build_path.exists() else {}
        if build.get('output_sha256') != output_hash:
            build = {}
        if build.get('manifest_sha256') and build['manifest_sha256'] != file_digest(manifest_json):
            errors.append('Manifest changed after the PDF build; rebuild before verifying')
        source_hash = file_digest(source_pdf)
        expected = manifest.get('document',{}).get('source_sha256') or build.get('source_sha256')
        if expected and expected != source_hash:
            errors.append('Source PDF does not match this manifest/build')
        if len(source) != len(dual) or len(manifest['pages']) != len(source):
            errors.append('Page count differs between source, manifest and output')
        chinese_by_page,all_text = [],[]
        for i,page in enumerate(dual):
            if i >= len(source):
                break
            s,d = source[i].rect,page.rect
            if abs(d.width-2*s.width) > .02 or abs(d.height-s.height) > .02:
                errors.append(f'Page {i+1}: size is not exactly 2x source width at source height')
            text = page.get_text(clip=fitz.Rect(0,0,s.width,s.height))
            all_text.append(text)
            chinese_by_page.append(cjk_count(text))
            spec = next((p for p in manifest['pages'] if p['page']==i+1),{})
            texts = [b.get('translation','') or '' for b in spec.get('blocks',[])]+[x.get('translation','') or '' for key in ('groups','overlays') for x in spec.get(key,[])]
            if any(cjk_count(t) for t in texts) and chinese_by_page[-1] == 0:
                errors.append(f'Page {i+1}: expected Chinese translation is not searchable')
        total = sum(chinese_by_page)
        if total < min_cjk:
            errors.append(f'Too little searchable Chinese text: {total} characters')
        font_ok,largest = embedded_cjk_font(dual,''.join(all_text))
        if not font_ok:
            errors.append('No embedded font containing the output Chinese characters was found')
        keys = build.get('page_keys') or [digest([output_hash,i]) for i in range(len(dual))]
        selected = choose_pages('all' if full else pages,len(dual),manifest['pages'])
        prior_path = Path(report_path) if report_path else dual_pdf.with_suffix('.qa.json')
        prior = read_json(prior_path) if prior_path.exists() else {}
        if pages == 'auto' and not full and len(prior.get('page_keys',[])) == len(keys):
            selected = sorted(set(selected) | {i+1 for i,(a,b) in enumerate(zip(keys,prior['page_keys'])) if a != b})
        # At least one source/right comparison even when previews are disabled.
        check_pages = list(range(1,len(source)+1)) if full else sorted({1,len(source)})
        diffs = right_half_difference(source,dual,check_pages) if len(source)==len(dual) else {}
        for number,difference in diffs.items():
            if difference > .5:
                errors.append(f'Page {number}: French half changed (aligned raster difference {difference:.2f})')
        warnings.extend(build.get('warnings',[]))
        preview = render_previews(dual,render_dir,selected,keys) if render_dir else {}
        report = {'source':str(Path(source_pdf).resolve()),'output':str(dual_pdf.resolve()),'output_sha256':output_hash,
                  'pages':len(dual),'mode':'full' if full else 'quick','searchable_cjk_characters':total,
                  'cjk_by_page':chinese_by_page,'embedded_cjk_font':font_ok,'largest_embedded_font_bytes':largest,
                  'unsupported_manifest_glyphs':missing,'right_half_differences':diffs,
                  'page_keys':keys,
                  'errors':errors,'warnings':list(dict.fromkeys(warnings)),**preview,
                  'visual_review':'Inspect overview sheets and selected/problem pages; not automatically certified',
                  'verify_seconds':round(time.perf_counter()-started,3)}
        write_json(report_path or dual_pdf.with_suffix('.qa.json'),report)
        print(f'{"PASS" if not errors else "FAIL"}: {len(dual)} pages, {total} searchable Chinese characters; {report["verify_seconds"]}s')
        if preview:
            print(f'Preview pages {selected}; newly rendered {preview["newly_rendered_pages"]}')
        for message in errors:
            print('ERROR:',message)
        if warnings:
            print(f'{len(set(warnings))} review notes in QA report')
        return report
    finally:
        source.close()
        dual.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source_pdf',type=Path)
    p.add_argument('manifest_json',type=Path)
    p.add_argument('dual_pdf',type=Path)
    p.add_argument('--render-dir',type=Path)
    p.add_argument('--pages',default='auto',help='auto, all, none or 1,3-5')
    p.add_argument('--full',action='store_true',help='Compare every French page and render every page when render-dir is supplied')
    p.add_argument('--report',type=Path)
    p.add_argument('--min-cjk',type=int,default=20)
    a = p.parse_args()
    result = verify(a.source_pdf,a.manifest_json,a.dual_pdf,a.render_dir,a.pages,a.full,a.report,a.min_cjk)
    if result['errors']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()

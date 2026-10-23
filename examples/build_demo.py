"""Build an original teaching example and check the bilingual PDF pipeline.

Run from the repository root:
    python -X utf8 examples/build_demo.py --output examples/output
"""
from pathlib import Path
import argparse
import subprocess
import sys
import tempfile

import pymupdf as fitz

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from prepare_manifest import prepare
from build_dual_pdf import build
from verify_dual_pdf import verify
from dual_common import Fonts, block_text, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'examples/output')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    source, dual = output / 'source.pdf', output / 'dual.pdf'
    blue = (.08, .28, .48)
    doc = fitz.open()
    p = doc.new_page(width=595.276, height=841.89)
    p.draw_rect((0, 0, 595.276, 11), fill=blue, color=None)
    p.insert_text((45, 50), 'PHYSIQUE / EXEMPLE ORIGINAL', fontsize=9, color=blue)
    p.insert_text((45, 93), 'Statique des fluides', fontsize=23, color=blue)
    p.insert_text((45, 123), 'Fiche de cours et exercice', fontsize=11, color=(.35, .4, .46))
    p.draw_line((45, 142), (550, 142), color=(.7, .79, .85), width=.8)
    p.insert_text((45, 179), '1. Pression dans un liquide', fontsize=15, color=blue)
    p.insert_text((45, 212), 'Dans un liquide au repos, la pression augmente avec la profondeur.', fontsize=11)
    p.insert_text((45, 233), 'La masse volumique est constante et le champ de pesanteur est uniforme.', fontsize=11)
    p.draw_rect((45, 257, 550, 319), color=(.7, .8, .9), fill=(.95, .97, 1), width=.6)
    fonts = Fonts()
    try:
        css = ('@font-face{font-family:DualCJK;src:url(cjk.ttf);}'
               '@font-face{font-family:DualMath;src:url(math.ttf);}'
               'body{font-family:DualCJK;font-size:18pt;text-align:center;margin:0;padding:0;}')
        spare, _ = p.insert_htmlbox((65, 270, 530, 309), fonts.rich('p(h) = p<sub>0</sub> + ρgh'),
                                   css=css, archive=fonts.archive)
        assert spare >= 0, 'Source equation did not fit'
    finally:
        fonts.close()
    p.insert_text((45, 346), 'avec h la profondeur mesuree depuis la surface libre.', fontsize=11)
    p.insert_text((45, 393), '2. Lecture du schema', fontsize=15, color=blue)
    p.draw_rect((87, 443, 318, 574), fill=(.88, .95, 1), color=None)
    p.draw_polyline([(87, 417), (87, 574), (318, 574), (318, 417)], color=blue, width=1.6)
    p.draw_line((87, 443), (318, 443), color=(.16, .54, .77), width=1)
    p.draw_circle((202, 533), 3, fill=blue, color=None)
    p.draw_line((202, 443), (202, 525), color=blue, width=.8)
    p.insert_text((214, 494), 'h', fontsize=12)
    p.insert_text((349, 448), 'Surface libre', fontsize=11)
    p.insert_text((349, 505), 'Liquide au repos', fontsize=11)
    p.draw_line((318, 443), (338, 443), color=(.45, .55, .65), width=.6)
    p.draw_line((286, 501), (338, 501), color=(.45, .55, .65), width=.6)
    p.insert_text((45, 625), '3. Exercice', fontsize=15, color=blue)
    p.insert_text((45, 658), 'Exprimer la difference de pression entre deux profondeurs.', fontsize=11)
    for y in (696, 728, 760):
        p.draw_line((45, y), (550, y), color=(.76, .8, .84), width=.5)
    p.insert_text((45, 807), 'Demonstration originale - aucune correction incluse', fontsize=8, color=(.4, .45, .5))
    p.insert_text((514, 824), 'Page 1', fontsize=8, color=(.4, .45, .5))
    doc.set_metadata({'title': 'Original demonstration: statique des fluides', 'author': 'translate-french-stem-pdf'})
    doc.subset_fonts()
    doc.save(source, garbage=4, deflate=True)
    doc.close()

    translations = {
        'PHYSIQUE / EXEMPLE ORIGINAL': '物理 / 原创示例',
        'Statique des fluides': '流体静力学',
        'Fiche de cours et exercice': '课程讲义与练习',
        '1. Pression dans un liquide': '1. 液体中的压强',
        'Dans un liquide au repos, la pression augmente avec la profondeur.': '静止液体中的压强随深度增加而增大。',
        'La masse volumique est constante et le champ de pesanteur est uniforme.': '假设液体密度为常量，重力场均匀。',
        'avec h la profondeur mesuree depuis la surface libre.': '其中 h 表示从自由液面向下测量的深度。',
        '2. Lecture du schema': '2. 示意图',
        'Surface libre': '自由液面',
        'Liquide au repos': '静止液体',
        '3. Exercice': '3. 练习',
        'Exprimer la difference de pression entre deux profondeurs.': '写出两个不同深度处的压强差表达式。',
        'Demonstration originale - aucune correction incluse': '原创演示 — 保留作答留白，不附解答',
    }
    with tempfile.TemporaryDirectory(prefix='dual-demo-') as td:
        work = Path(td)
        manifest_path, updates_path = work / 'manifest.json', work / 'updates.json'
        manifest = prepare(source, manifest_path)
        # This fixture owns its source: every prose block must have a known translation.
        blocks = {}
        for page in manifest['pages']:
            for b in page['blocks']:
                if b['source'].startswith('p(h) ='):
                    blocks[f'{page["page"]}:{b["id"]}'] = {'action': 'preserve', 'reason': 'Standalone source equation'}
                    continue
                if b['action'] == 'translate':
                    assert b['source'] in translations, f'Untranslated demo block: {b["source"]!r}'
        write_json(updates_path, {'source_translations': translations, 'blocks': blocks})
        command = [sys.executable, '-X', 'utf8', str(ROOT / 'scripts/apply_translations.py'),
                   str(manifest_path), str(updates_path)]
        subprocess.run(command, check=True)
        first = manifest_path.read_bytes()
        subprocess.run(command, check=True)
        assert manifest_path.read_bytes() == first, 'Repeated updates changed the manifest'
        built = build(source, manifest_path, dual)
        report = verify(source, manifest_path, dual, work / 'previews', full=True)
        assert not report['errors'], report['errors']
        assert all(v == 0 for v in report['right_half_differences'].values()), 'French half changed'
        cached = verify(source, manifest_path, dual, work / 'previews', full=True)
        assert cached['newly_rendered_pages'] == [], 'Unchanged preview was rebuilt'
        with fitz.open(source) as s, fitz.open(dual) as d:
            assert abs(d[0].rect.width - 2*s[0].rect.width) < .02
            assert '流体静力学' in d[0].get_text(), 'Chinese title is not searchable'
            # All source equation blocks remain available, rather than being retyped.
            original = [block_text(b) for b in s[0].get_text('dict')['blocks'] if b.get('type') == 0]
            assert any('ρgh' in t.replace(' ', '') for t in original)
            d[0].get_pixmap(matrix=fitz.Matrix(1.3, 1.3), alpha=False).save(output / 'preview.png')
        assert max(x['font_size'] for x in built['placements']) >= 20, 'Title hierarchy lost'
        print('PASS: translated prose, searchable Chinese, title hierarchy, preserved French, idempotent updates and cached previews')
        print(f'Demo: {output}')


if __name__ == '__main__':
    main()

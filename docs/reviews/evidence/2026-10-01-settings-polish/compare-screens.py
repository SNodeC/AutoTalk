"""Make labelled before/after review sheets; report full-image differences."""
import json
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw

root = Path('docs/reviews/evidence/2026-10-01-settings-polish')
out = root / 'comparisons'
out.mkdir(exist_ok=True)
records = []
for stack in ('wheel', 'native'):
    for scale in ('1', '1.5'):
        sheet = Image.new('RGB', (1600, 1880), '#dddddd')
        draw = ImageDraw.Draw(sheet)
        for row, (theme, main, dialog) in enumerate(
            (t, m, d) for t in ('light', 'dark') for m, d in ((940, 760), (1100, 920))
        ):
            for kind, width in (('inspector', main), ('timing', dialog)):
                name = f'{kind}-{theme}-{width}-scale{scale}.png'
                before = Image.open(root / 'screens/before' / stack / name).convert('RGB')
                after = Image.open(root / 'screens/after' / stack / name).convert('RGB')
                assert before.size == after.size
                bbox = ImageChops.difference(before, after).getbbox()
                records.append({'stack': stack, 'file': name, 'difference_bbox': bbox})
                for phase, image in (('before', before), ('after', after)):
                    column = (0 if kind == 'inspector' else 2) + (phase == 'after')
                    if kind == 'inspector':
                        factor = float(scale)
                        image = image.crop((image.width - round(230 * factor), round(195 * factor),
                                            image.width, image.height - round(110 * factor)))
                    image.thumbnail((390, 430))
                    x, y = column * 400, row * 470
                    draw.text((x + 4, y + 4), f'{stack} {scale}x {theme} {width} {kind} {phase}', fill='black')
                    sheet.paste(image, (x + 4, y + 24))
        sheet.save(out / f'{stack}-{scale}.png')
(out / 'diffs.json').write_text(json.dumps(records, indent=2))
print(f'Compared {len(records)} before/after pairs; four review sheets written.')

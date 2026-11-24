from pathlib import Path
from PIL import Image, ImageDraw

directory = Path('output/rendered')
files = sorted(directory.glob('page-*.png'), key=lambda p: int(p.stem.split('-')[-1]))
for start in range(0, len(files), 10):
    batch = files[start:start + 10]
    sheet = Image.new('RGB', (5 * 190, 2 * 270), '#e6ebef')
    draw = ImageDraw.Draw(sheet)
    for offset, path in enumerate(batch):
        im = Image.open(path).convert('RGB')
        im.thumbnail((180, 240))
        x, y = (offset % 5) * 190 + 5, (offset // 5) * 270 + 20
        sheet.paste(im, (x, y))
        draw.text((x, y - 15), f'Page {start + offset + 1}', fill='#102a43')
    sheet.save(directory / f'sheet-{start // 10 + 1:02}.png')
print('contact sheets', (len(files) + 9) // 10)

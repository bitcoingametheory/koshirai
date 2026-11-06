"""Fetch hash-bound public full pages outside this checkout."""
import argparse
import hashlib
import io
import json
import urllib.request
from pathlib import Path


def fetch(cohort, destination):
    from PIL import Image
    destination = Path(destination).expanduser().resolve()
    checkout = Path(__file__).resolve().parents[1]
    if destination == checkout or destination.is_relative_to(checkout):
        raise ValueError('Image storage must be outside the public checkout')
    destination.mkdir(parents=True, exist_ok=True)
    frames = {}
    for example in cohort['examples']:
        identifier = example['id']
        if not identifier or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for c in identifier):
            raise ValueError('Unsafe example ID')
        source = example['source']
        url = source['url']
        if not url.startswith('https://'):
            raise ValueError('Public HTTPS image URL required')
        expected = source['sha256']
        if expected not in frames:
            cached = destination / (expected + '.frame')
            if cached.exists():
                raw = cached.read_bytes()
            else:
                request = urllib.request.Request(url, headers={'User-Agent': 'koshirai-public-pilot/1'})
                with urllib.request.urlopen(request, timeout=60) as response:
                    raw = response.read(100_000_001)
            if len(raw) > 100_000_000 or hashlib.sha256(raw).hexdigest() != expected:
                raise ValueError('Frame hash or size mismatch: ' + identifier)
            cached.write_bytes(raw)
            frames[expected] = raw
        if 'box' not in example:
            with Image.open(io.BytesIO(frames[expected])) as image:
                if image.width * image.height > 40_000_000:
                    raise ValueError('Full page exceeds 40M pixel bound')
            (destination / (identifier + '.jpg')).write_bytes(frames[expected])
            continue
        with Image.open(io.BytesIO(frames[expected])) as image:
            box = example['box']
            if (len(box) != 4 or any(type(n) is not int for n in box)
                    or not 0 <= box[0] < box[2] <= image.width
                    or not 0 <= box[1] < box[3] <= image.height):
                raise ValueError('Invalid native-pixel crop: ' + identifier)
            buffer = io.BytesIO()
            image.crop(box).convert('RGB').save(buffer, format='PNG')
        raw = buffer.getvalue()
        if hashlib.sha256(raw).hexdigest() != example['crop_sha256']:
            raise ValueError('Crop hash mismatch (check Pillow version): ' + identifier)
        (destination / (identifier + '.png')).write_bytes(raw)
    return len(cohort['examples'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort', type=Path, default=Path(__file__).with_name('sample_manifest.json'))
    parser.add_argument('--images', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps({'images': fetch(json.loads(args.cohort.read_text()), args.images)}))

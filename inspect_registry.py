"""Inspect a real local registry CSV without guessing its schema or identifiers."""
import argparse
import csv
import hashlib
import io
import json
import re
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('csv_path', type=Path)
    p.add_argument('--area-column')
    p.add_argument('--area-value')
    p.add_argument('--encoding', default='utf-8-sig')
    args = p.parse_args()
    if bool(args.area_column) != bool(args.area_value):
        p.error('Supply both --area-column and --area-value, or neither.')
    raw = args.csv_path.read_bytes()
    if not raw.strip():
        p.error('Input CSV is empty.')
    text = raw.decode(args.encoding)
    if text.lstrip().lower().startswith(('<!doctype', '<html')):
        p.error('Input is HTML, not a registry CSV.')
    reader = csv.DictReader(io.StringIO(text))
    columns = reader.fieldnames
    if not columns or len(columns) != len(set(columns)):
        p.error('CSV needs nonempty, unique headers.')
    rows = list(reader)
    if not rows:
        p.error('CSV contains no data rows.')
    if any(None in r or any(v is None for v in r.values()) for r in rows):
        p.error('Malformed CSV: row lengths differ from headers.')
    print(json.dumps({'sha256': hashlib.sha256(raw).hexdigest(),
                      'columns': columns, 'total_rows': len(rows)}, indent=2))
    hints = [c for c in columns if re.search(r'area|project|plot|parcel|property|land|munc|municip', c, re.I)]
    print('Candidate descriptive/link fields (not verified keys):', json.dumps(hints))
    for c in hints:
        hits = sorted({r[c] for r in rows if 'furjan' in r[c].casefold()})
        if hits:
            print('Furjan text candidates:', json.dumps({c: hits[:30]}, ensure_ascii=False))
    if not args.area_column:
        print('Schema inspected. Choose an explicit verified column/value to print the filtered sample.')
        return
    if args.area_column not in columns:
        p.error('Area column not in the actual CSV headers.')
    selected = [r for r in rows if r[args.area_column].strip().casefold() == args.area_value.strip().casefold()]
    if not selected:
        p.error('Exact filter returned zero rows; do not infer a pilot list.')
    sensitive = re.compile(r'escrow|account|phone|mobile|email|fax|passport|emirates|owner|buyer|seller', re.I)
    sample = [{c: ('[REDACTED]' if sensitive.search(c) else r[c]) for c in columns} for r in selected[:10]]
    print(json.dumps({'filtered_rows': len(selected), 'sample': sample}, indent=2, ensure_ascii=False))
    print('No plot match established. Review identifiers, duplicates and geometry source before joining.')


if __name__ == '__main__':
    main()

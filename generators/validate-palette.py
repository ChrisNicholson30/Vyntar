#!/usr/bin/env python3
from theme_core import load, contrast_report
rows = contrast_report(load())
for row in rows:
    if row[3] < row[4]:
        raise SystemExit('Contrast failure: '+repr(row))
print('%d contrast pairs pass; minimum %.2f:1.' % (len(rows), min(r[3] for r in rows)))

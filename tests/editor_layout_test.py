#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""The CS-1 Programmer's text stays inside its boxes, whatever font the computer substitutes: the page in headless
Chromium with its own font, then with a deliberately wide, heavy one forced on everything (the worst a fallback does),
at desktop and phone widths, through every factory sound (the value names change).

    python3 tests/editor_layout_test.py [build/editor/cs1-editor.html] [out-dir]"""
import os, sys, tempfile
from playwright.sync_api import sync_playwright

PAGE = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "build/editor/cs1-editor.html")
OUT = sys.argv[2] if len(sys.argv) > 2 else tempfile.mkdtemp()
WIDE = "* { font-family: 'DejaVu Sans', Verdana, sans-serif !important; font-weight: 800 !important; letter-spacing: .07em !important; }"
OVERFLOW = """() => {          // where the text is drawn (a range's box), not the element's: clipped text counts as cut
  const bad = [];
  const ink = (e) => { const r = document.createRange(); r.selectNodeContents(e); return r.getBoundingClientRect(); };
  const inside = (q, r) => q.width === 0 || (q.left >= r.left - 1 && q.right <= r.right + 1 && q.top >= r.top - 1 && q.bottom <= r.bottom + 1);
  const check = (e, box) => { if (!e.offsetParent || !e.textContent.trim()) return;
    if (!inside(ink(e), box.getBoundingClientRect())) bad.push((e.className || e.tagName) + ': ' + e.textContent.trim().slice(0, 20)); };
  for (const sl of document.querySelectorAll('.sl')) for (const e of sl.querySelectorAll('.leg, .nm, .val')) { check(e, e); check(e, sl); }
  for (const e of document.querySelectorAll('.tbtn, .slot .acts button, .top .btn, .lib-head .btn, .tone-more')) check(e, e);
  for (const e of document.querySelectorAll('.slot .sn, .slot .no')) check(e, e.closest('.slot'));
  for (const s of document.querySelectorAll('.slot')) { const r = s.getBoundingClientRect();
    for (const b of s.querySelectorAll('button')) if (!inside(b.getBoundingClientRect(), r)) bad.push('slot button out: ' + b.textContent); }
  for (const row of document.querySelectorAll('.knobs')) { const k = [...row.children];
    for (let i = 1; i < k.length; i++) if (k[i].getBoundingClientRect().left < k[i - 1].getBoundingClientRect().right - 0.5) bad.push('sliders overlap'); }
  if (document.documentElement.scrollWidth > innerWidth + 1) bad.push('sideways scroll');
  return bad;
}"""
fails = 0
with sync_playwright() as p:
    br = p.chromium.launch()
    for label, css, w, h in (("own font, desktop", None, 1440, 1000), ("wide font, desktop", WIDE, 1440, 1000),
                             ("wide font, 1280", WIDE, 1280, 900), ("wide font, phone", WIDE, 390, 844)):
        pg = br.new_page(viewport={"width": w, "height": h})
        pg.goto("file://" + PAGE)
        if css:
            pg.add_style_tag(content=css)
        pg.wait_for_timeout(200)
        pg.evaluate("() => typeof fitAll === \"function\" && fitAll()")
        bad = set()
        for i in range(69):                               # every factory sound: the named values change
            pg.evaluate(f"() => {{ $('factory').value = '{i}'; $('factory').onchange(); }}")
            bad.update(pg.evaluate(OVERFLOW))
        ok = not bad
        fails += not ok
        print(f"layout: {label:<24} {'ok' if ok else 'FAIL ' + str(sorted(bad)[:8])}")
        pg.evaluate("() => { $('factory').value = '62'; $('factory').onchange(); }")
        pg.screenshot(path=f"{OUT}/{label.replace(' ', '-').replace(',', '')}.png", full_page=(w > 500))
        pg.close()
    br.close()
print("layout:", "all ok" if not fails else f"{fails} FAILED", "· screenshots in", OUT)
sys.exit(1 if fails else 0)

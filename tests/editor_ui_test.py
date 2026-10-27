#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""The CS-1 Programmer (build/editor/cs1-editor.html) in headless Chromium, against a simulated FM-1: a second copy
of the firmware (the page's own cs1.wasm) behind a fake Web MIDI port, answering the editor link as the device does.

    python3 tests/editor_ui_test.py [build/editor/cs1-editor.html] [out-dir for screenshots]

Needs Playwright with Chromium (pip install playwright; playwright install chromium)."""
import json, os, sys, tempfile
from playwright.sync_api import sync_playwright

PAGE = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "build/editor/cs1-editor.html")
OUT = sys.argv[2] if len(sys.argv) > 2 else tempfile.mkdtemp()
fails = 0


def check(what, ok):
    global fails
    print(f"ui: {what:<72} {'ok' if ok else 'FAIL'}")
    if not ok:
        fails += 1


# the simulated FM-1: the firmware in wasm, its clock run on a timer; SysEx and notes in, SysEx out to the page
FAKE_MIDI = r"""
(() => {
  const dev = { ex: null, inPort: null, log: [], notes: 0 };
  window.__fm1 = dev;
  async function boot() {
    const bin = Uint8Array.from(atob(WASM_B64), (c) => c.charCodeAt(0));
    const { instance } = await WebAssembly.instantiate(bin, {});
    const ex = instance.exports;
    if (ex._initialize) ex._initialize();
    ex.web_boot();
    dev.ex = ex;
    setInterval(() => {
      ex.web_render(441);                                   // 10 ms of device time a tick
      let n;
      while ((n = ex.web_sysex_out_take())) {
        const f = new Uint8Array(ex.memory.buffer, ex.web_sysex_out_buf(), n).slice();
        if (dev.inPort && dev.inPort.onmidimessage) dev.inPort.onmidimessage({ data: f });
      }
      while (ex.web_midi_out_take()) {}
    }, 5);
  }
  const queue = [];
  setInterval(() => {                                       // the device takes one frame at a time
    if (!dev.ex) return;
    while (queue.length) {
      const f = queue[0];
      const buf = new Uint8Array(dev.ex.memory.buffer, dev.ex.web_sysex_buf(), 640);
      buf.set(f);
      if (!dev.ex.web_sysex(f.length)) break;
      queue.shift();
    }
  }, 2);
  const out = { id: "fm1-out", name: "FM-1", manufacturer: "M-VAVE",
    send(d) { d = Uint8Array.from(d); dev.log.push(d[0] === 0xF0 ? d[5] : d[0]);
      if (d[0] === 0xF0) queue.push(d);
      else { if ((d[0] & 0xF0) === 0x90) dev.notes++; if (dev.ex) dev.ex.web_midi(d[0], d[1] | 0, d[2] | 0); } } };
  const inp = { id: "fm1-in", name: "FM-1", manufacturer: "M-VAVE", onmidimessage: null };
  dev.inPort = inp;
  navigator.requestMIDIAccess = async () => { if (!dev.ex) await boot();
    return { outputs: new Map([[out.id, out]]), inputs: new Map([[inp.id, inp]]), onstatechange: null }; };
})();
"""

DEVICE_PANEL = """() => new Promise((resolve) => {     // the simulated FM-1's panel, asked over its own SysEx
  const ex = window.__fm1.ex, f = [0xF0, 0x7D, 0x43, 0x53, 0x31, 0x02, 0xF7];
  new Uint8Array(ex.memory.buffer, ex.web_sysex_buf(), 640).set(f); ex.web_sysex(f.length);
  const prev = window.__fm1.inPort.onmidimessage;
  window.__fm1.inPort.onmidimessage = (e) => { if (e.data[5] === 0x42) { window.__fm1.inPort.onmidimessage = prev; resolve(Array.from(e.data.slice(6, -1))); } else if (prev) prev(e); };
})"""
DEVICE_SLOT = """(i) => { const ex = window.__fm1.ex, b = new Uint8Array(ex.memory.buffer, ex.web_bank(), 4096);
  return Array.from(b.slice(i * 128, i * 128 + 128)); }"""

with sync_playwright() as p:
    br = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    ctx = br.new_context(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
    ctx.add_init_script(FAKE_MIDI)
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.goto("file://" + PAGE)
    pg.wait_for_timeout(400)
    check("the page loads without script errors", not errors)
    n_sl = pg.locator(".sl").count()
    check(f"every knob of a sound is on the panel ({n_sl} sliders)", n_sl == 2 * 26 + 4 + 6 + 4 + 4 + 5 + 4 + 4 + 4 + 3 + 7 + 5 + 4)
    check("22 tone buttons, 69 factory sounds", pg.locator(".tbtn").count() == 22 and pg.locator("#factory option").count() == 70)
    check("32 user slots", pg.locator(".slot").count() == 32)
    pg.screenshot(path=f"{OUT}/desktop.png", full_page=True)

    # ---- the browser's sound: the real engine plays a note
    pg.click("#audio")
    pg.wait_for_function("document.querySelector('#audioLed').classList.contains('on')", timeout=8000)
    rms = pg.evaluate("""async () => {
      const an = eng.ctx.createAnalyser(); an.fftSize = 2048; eng.gain.connect(an);
      const buf = new Float32Array(2048), level = () => { an.getFloatTimeDomainData(buf); return Math.sqrt(buf.reduce((s, v) => s + v * v, 0) / buf.length); };
      await new Promise((r) => setTimeout(r, 300)); const quiet = level();
      noteOn(60); await new Promise((r) => setTimeout(r, 700)); const loud = level(); noteOff(60);
      return [quiet, loud]; }""")
    check(f"the browser engine is silent, then a note sounds (rms {rms[1]:.3f})", rms[0] < 0.002 and rms[1] > 0.01)
    lv = pg.evaluate("""async () => {          // closing both LPFs: the engine follows the sliders (the sine skips the filters)
      const an = eng.ctx.createAnalyser(); an.fftSize = 4096; eng.gain.connect(an);
      const buf = new Float32Array(4096), level = () => { an.getFloatTimeDomainData(buf); return Math.sqrt(buf.reduce((s, v) => s + v * v, 0) / buf.length); };
      noteOn(57); await new Promise((r) => setTimeout(r, 700)); const open = level();
      setParam(11, 10); setParam(26 + 11, 10); await new Promise((r) => setTimeout(r, 600)); const shut = level(); noteOff(57);
      return [open, shut]; }""")
    check(f"closing both LPF sliders darkens the browser's sound ({lv[1] / lv[0]:.2f} of the level)", lv[1] < lv[0] * 0.5)
    pg.evaluate("() => { $('factory').value = '0'; $('factory').onchange(); }")

    # ---- the FM-1: connect, live, get, send
    pg.click("#connect")
    pg.wait_for_function("document.querySelector('#fmLed').classList.contains('on')", timeout=5000)
    check("Connect finds the FM-1 and it answers HELLO", "CS-1" in pg.inner_text("#fwInfo"))
    pg.click("#live")
    pg.wait_for_timeout(400)
    dev = pg.evaluate(DEVICE_PANEL)
    ed = pg.evaluate("() => [...S.patch]")
    check("Live sends the whole sound at once", dev[3:] == ed)
    # drag channel II's LPF slider (the 12th slider of channel II) down with the mouse
    tr = pg.locator("#chan1 .sl .track").nth(9)       # VCO 6, VCF: HPF, RES.H, LPF -> index 6 + 2 = 8 .. check by name
    names = pg.eval_on_selector_all("#chan1 .sl .nm", "els => els.map(e => e.textContent)")
    i_lpf = names.index("LPF")
    tr = pg.locator("#chan1 .sl .track").nth(i_lpf)
    box = tr.bounding_box()
    pg.mouse.move(box["x"] + box["width"] / 2, box["y"] + 20)
    pg.mouse.down()
    for k in range(12):
        pg.mouse.move(box["x"] + box["width"] / 2, box["y"] + 20 + k * 6, steps=2)
        pg.wait_for_timeout(15)
    pg.mouse.up()
    pg.wait_for_timeout(900)                             # the drag, then the read-back that checks it
    dev = pg.evaluate(DEVICE_PANEL)
    ed = pg.evaluate("() => [...S.patch]")
    check(f"dragging channel II's LPF reaches the FM-1 live (now {ed[26 + 11]})", dev[3 + 26 + 11] == ed[26 + 11] and ed[26 + 11] < 110 and dev[3:] == ed)
    # a tone button: channel I gets BRASS 1's panel, the FM-1 the same
    pg.locator("#chan0 .tbtn").nth(2).click()           # row I third button: BRASS 1 (tone 4)
    pg.wait_for_timeout(500)
    dev = pg.evaluate(DEVICE_PANEL)
    check("a tone button loads the tone and the FM-1 follows (tone and panel)", dev[0] == 4 and dev[3:] == pg.evaluate("() => [...S.patch]"))
    # change the FM-1 behind the editor's back, then Get
    pg.evaluate("""() => { const ex = window.__fm1.ex, f = [0xF0,0x7D,0x43,0x53,0x31,0x08,10,0xF7];
      new Uint8Array(ex.memory.buffer, ex.web_sysex_buf(), 640).set(f); ex.web_sysex(f.length); }""")
    pg.wait_for_timeout(300)
    pg.click("#live")                                   # (live off: Get must not echo back)
    pg.click("#getFm")
    pg.wait_for_timeout(400)
    sounds = json.loads(pg.evaluate("() => JSON.stringify(DATA.sounds.map(s => s.name))"))
    check(f"Get from FM-1 reads its sound ({pg.input_value('#pname')})", pg.input_value("#pname") == sounds[10]
          and pg.evaluate("() => [...S.patch]") == pg.evaluate("() => DATA.sounds[10].patch"))

    # ---- slots: store, read all, write all
    pg.on("dialog", lambda d: d.accept())
    pg.locator(".slot").nth(4).locator("[data-a=store]").click()
    pg.wait_for_timeout(600)
    sl = pg.evaluate(DEVICE_SLOT, 4)
    check("Store on U05 writes the FM-1's slot 5 (flash)", sl[0] == 0xA7 and sl[5:5 + 107] == pg.evaluate("() => [...S.patch]"))
    pg.evaluate("() => { S.slots = new Array(32).fill(null); drawSlots(); }")
    pg.click("#readAll")
    pg.wait_for_function("document.querySelector('#status').textContent.startsWith('Read all')", timeout=20000)
    check("Read all brings the FM-1's slot back into U05", pg.evaluate("() => S.slots[4] && S.slots[4].patch.length") == 107)
    pg.evaluate("() => { S.slots[7] = { name: 'TEST EIGHT', tones: [2, 3], cat: 0, patch: DATA.sounds[3].patch.slice() }; drawSlots(); }")
    pg.click("#writeAll")
    pg.wait_for_timeout(1500)
    sl = pg.evaluate(DEVICE_SLOT, 7)
    check("Write all puts U08 on the FM-1", sl[0] == 0xA7 and sl[1:3] == [2, 3] and sl[5:5 + 107] == pg.evaluate("() => DATA.sounds[3].patch"))

    # ---- files: download one, download all, the .cs1bank, and open them again
    with pg.expect_download() as d:
        pg.click("#dlPatch")
    pf = os.path.join(OUT, d.value.suggested_filename); d.value.save_as(pf)
    doc = json.load(open(pf))
    check(f"Download sound: {d.value.suggested_filename}, the patch inside", doc["format"] == "cs1-patch" and len(doc["patch"]) == 107)
    with pg.expect_download() as d:
        pg.click("#dlAll")
    lf = os.path.join(OUT, d.value.suggested_filename); d.value.save_as(lf)
    lib = json.load(open(lf))
    check("Download all: a .cs1lib with the 32 slots and their names", lib["format"] == "cs1-library" and len(lib["slots"]) == 32 and lib["slots"][7]["name"] == "TEST EIGHT")
    with pg.expect_download() as d:
        pg.click("#dlBank")
    bf = os.path.join(OUT, d.value.suggested_filename); d.value.save_as(bf)
    bank = open(bf, "rb").read()
    check("Download .cs1bank: 4096 bytes, U08 as the firmware lays it out", len(bank) == 4096 and bank[7 * 128] == 0xA7 and list(bank[7 * 128 + 5:7 * 128 + 112]) == pg.evaluate("() => DATA.sounds[3].patch"))
    pg.evaluate("() => { $('factory').value = '20'; $('factory').onchange(); }")
    pg.set_input_files("#fileIn", pf)
    pg.wait_for_timeout(200)
    check("Open file: the downloaded sound comes back", pg.evaluate("() => [...S.patch]") == doc["patch"] and pg.input_value("#pname") == doc["name"])
    pg.evaluate("() => { S.slots = new Array(32).fill(null); drawSlots(); }")
    pg.evaluate("() => { fileTarget = 'bank'; }")
    pg.set_input_files("#fileIn", lf)
    pg.wait_for_timeout(200)
    check("Open bank (.cs1lib): the slots and names come back", pg.evaluate("() => S.slots[7] && S.slots[7].name") == "TEST EIGHT")
    pg.evaluate("() => { S.slots = new Array(32).fill(null); drawSlots(); fileTarget = 'bank'; }")
    pg.set_input_files("#fileIn", bf)
    pg.wait_for_timeout(200)
    check("Open bank (.cs1bank): the slots come back", pg.evaluate("() => S.slots[7] && S.slots[7].patch.join()") == ",".join(map(str, pg.evaluate("() => DATA.sounds[3].patch"))))
    bad = os.path.join(OUT, "bad.cs1patch"); open(bad, "w").write('{"format":"cs1-patch","patch":[1,2,3],"tones":[0,0]}')
    pg.set_input_files("#fileIn", bad)
    pg.wait_for_timeout(200)
    check("a damaged file is refused with a message", "Could not open" in pg.inner_text("#status"))

    # ---- it survives a reload (the panel and the slots are kept in the browser)
    keep = pg.evaluate("() => [...S.patch]")
    pg.wait_for_timeout(400)
    pg.reload(); pg.wait_for_timeout(500)
    check("a reload keeps the panel and the slots", pg.evaluate("() => [...S.patch]") == keep and pg.evaluate("() => S.slots.filter(Boolean).length") >= 1)
    check("no script errors along the way", not errors)
    if errors: print("\n".join(errors[:10]))

    m = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    mp = m.new_page(); mp.goto("file://" + PAGE); mp.wait_for_timeout(300)
    check("on a phone: no sideways scrolling", mp.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1"))
    mp.screenshot(path=f"{OUT}/phone.png", full_page=False)
    br.close()

print(f"ui: screenshots in {OUT}")
print("ui:", "all ok" if not fails else f"{fails} FAILED")
sys.exit(1 if fails else 0)

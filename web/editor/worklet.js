// SPDX-License-Identifier: GPL-3.0-only
// The editor's sound: the CS-1 firmware (cs1.wasm, web/emu/cs1_web.c against the fake FM-1) in an AudioWorklet, as
// web/emu/worklet.js runs it, minus the screen and the panel: the editor feeds it SysEx (the editor link, the same
// frames the FM-1 takes) and MIDI, and it renders. web/editor/build.sh puts this file inside the page.
class CS1Editor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ex = null;
    this.pending = [];                        // SysEx frames the firmware's queue could not take yet
    this.port.onmessage = (e) => this.onMessage(e.data);
  }
  async onMessage(m) {
    if (m.type === "load") {
      try {
        const { instance } = await WebAssembly.instantiate(m.wasm, {});
        const ex = instance.exports;
        if (ex._initialize) ex._initialize();
        ex.web_master(1023);
        ex.web_boot();
        this.ex = ex;
        this.port.postMessage({ type: "ready" });
      } catch (err) {
        this.port.postMessage({ type: "error", message: String((err && err.message) || err) });
      }
      return;
    }
    if (!this.ex) return;
    if (m.type === "sysex") this.pending.push(m.data);
    else if (m.type === "midi") this.ex.web_midi(m.data[0] | 0, m.data[1] | 0, m.data[2] | 0);
  }
  feed() {                                    // between quanta: as many frames as the firmware's queue takes
    const ex = this.ex;
    while (this.pending.length) {
      const f = this.pending[0];
      const buf = new Uint8Array(ex.memory.buffer, ex.web_sysex_buf(), 640);
      buf.set(f.subarray(0, 640));
      if (!ex.web_sysex(Math.min(f.length, 640))) break;   // full: after the next quantum
      this.pending.shift();
    }
    while (ex.web_sysex_out_take()) {}        // (its replies: the editor trusts its own copy of the panel)
    while (ex.web_midi_out_take()) {}
  }
  process(inputs, outputs) {
    const ex = this.ex;
    if (!ex) return true;
    this.feed();
    const out = outputs[0], n = out[0].length;
    ex.web_render(n);
    out[0].set(new Float32Array(ex.memory.buffer, ex.web_out_l(), n));
    if (out[1]) out[1].set(new Float32Array(ex.memory.buffer, ex.web_out_r(), n));
    return true;
  }
}
registerProcessor("cs1-editor", CS1Editor);

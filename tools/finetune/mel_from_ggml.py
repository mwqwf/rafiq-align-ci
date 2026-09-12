# -*- coding: utf-8 -*-
"""يجهّز ما يحتاجه convert-h5-to-ggml دون تنزيل: مرشّحاتُ الميل من ملفِّ المحرك نفسِه."""
import json, os, struct, sys
import numpy as np

ROOT = r"C:\Users\slxc\Documents\GitHub\QuranRafiq"
SRC  = os.path.join(ROOT, "tools", "tasmi_bench", "work", "ggml-q8.bin")
OUT  = sys.argv[1]

f = open(SRC, "rb")
magic = struct.unpack("i", f.read(4))[0]
assert magic == 0x67676d6c, hex(magic)
hp = struct.unpack("i"*11, f.read(44))
n_mel_rows, n_mel_cols = struct.unpack("ii", f.read(8))
filters = np.frombuffer(f.read(4*n_mel_rows*n_mel_cols), dtype=np.float32).reshape(n_mel_rows, n_mel_cols)
f.close()
print("hparams:", hp)
print("filters:", filters.shape, "sum=%.4f" % filters.sum())

d = os.path.join(OUT, "whisper", "assets")
os.makedirs(d, exist_ok=True)
np.savez(os.path.join(d, "mel_filters.npz"), **{f"mel_{n_mel_rows}": filters})
print("wrote", os.path.join(d, "mel_filters.npz"))

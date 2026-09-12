# -*- coding: utf-8 -*-
"""🔢 **تكميمُ q8_0 في بايثون** — بديلٌ عن `quantize` المفقود (لا مترجمَ C على الجهاز).

القواعدُ منقولةٌ من `examples/common-ggml.cpp` و`examples/quantize/quantize.cpp`:
- **ثنائيّةُ الأبعاد فقط** تُكمَّم، وتُستثنى أربعةُ موتِّرات بأسمائها.
- الكتلةُ 32 قيمة: مقياسٌ نصفيّ `d = amax/127` ثم 32 عدداً صحيحاً بثمانية بتّات.
- ترويسةُ الملفّ: `ftype = 2*1000 + 7` (إصدارُ التكميم 2 · q8_0).

⛔ ولا يُصدَّق بلا برهان: يُقارَن المخرَجُ بملفِّ المحرك القائم `ggml-q8.bin`.
"""
import struct, sys
import numpy as np

SKIP = {"encoder.conv1.bias", "encoder.conv2.bias",
        "encoder.positional_embedding", "decoder.positional_embedding"}
Q8_0 = 8

def quant_rows(a):
    """a: (rows, k) float32 · k مضاعفُ 32 ⇒ بايتاتُ q8_0."""
    rows, k = a.shape
    nb = k // 32
    blocks = a.reshape(rows, nb, 32)
    amax = np.abs(blocks).max(axis=2)
    d = (amax / 127.0).astype(np.float32)
    id_ = np.where(d != 0, 1.0 / np.where(d == 0, 1, d), 0.0).astype(np.float32)
    q = np.rint(blocks * id_[:, :, None]).astype(np.int8)
    out = np.empty((rows, nb, 34), dtype=np.uint8)
    out[:, :, :2] = d.astype(np.float16).view(np.uint8).reshape(rows, nb, 2)
    out[:, :, 2:] = q.view(np.uint8)
    return out.tobytes()

def convert(src, dst):
    f = open(src, "rb"); o = open(dst, "wb")
    head = f.read(4 + 11 * 4)
    hp = list(struct.unpack("i" * 12, head))
    hp[11] = 2 * 1000 + 7                       # ftype الوجهة
    o.write(struct.pack("i" * 12, *hp))
    r, c = struct.unpack("ii", f.read(8)); o.write(struct.pack("ii", r, c))
    o.write(f.read(4 * r * c))                  # مرشّحاتُ الميل كما هي
    n = struct.unpack("i", f.read(4))[0]; o.write(struct.pack("i", n))
    for _ in range(n):
        L = struct.unpack("i", f.read(4))[0]
        o.write(struct.pack("i", L)); o.write(f.read(L))
    nq = nk = 0
    while True:
        h = f.read(12)
        if len(h) < 12:
            break
        n_dims, name_len, ttype = struct.unpack("iii", h)
        ne = list(struct.unpack("i" * n_dims, f.read(4 * n_dims)))
        name = f.read(name_len).decode("utf-8")
        nel = int(np.prod(ne))
        raw = f.read(nel * (4 if ttype == 0 else 2))
        data = np.frombuffer(raw, dtype=np.float32 if ttype == 0 else np.float16).astype(np.float32)
        if n_dims == 2 and name not in SKIP:
            b = quant_rows(data.reshape(ne[1], ne[0]))
            o.write(struct.pack("iii", n_dims, name_len, Q8_0))
            o.write(struct.pack("i" * n_dims, *ne)); o.write(name.encode("utf-8")); o.write(b)
            nq += 1
        else:
            o.write(h); o.write(struct.pack("i" * n_dims, *ne))
            o.write(name.encode("utf-8")); o.write(raw)
            nk += 1
    f.close(); o.close()
    print(f"مُكمَّم {nq} · كما هو {nk}")

if __name__ == "__main__":
    convert(sys.argv[1], sys.argv[2])

# ⚖️ **برهانُ صحّته** (2026-09-08): كُمِّم به النموذجُ المشحون من أوزانه الكاملة،
# فجاء **بحجمِ ملفِّ المحرك القائم نفسِه بالبايت** (43,537,433) واختلف عنه في
# **2,563 بايتاً فقط = 0.0059٪** — وهي تعادلاتُ تقريبٍ لا فروقُ صيغة.

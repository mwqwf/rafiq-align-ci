"""نزع ID3 الداخلي عند حدود إطارات MPEG كاملة فقط؛ بلا تخطي تلف الصوت."""


def _frame_size(data, pos):
    if pos + 4 > len(data):
        return None
    a, b, c, d = data[pos:pos + 4]
    if a != 255 or b & 224 != 224:
        return None
    ver, layer = (b >> 3) & 3, (b >> 1) & 3
    bi, si, pad = c >> 4, (c >> 2) & 3, (c >> 1) & 1
    if ver == 1 or layer != 1 or bi in (0, 15) or si == 3 or d & 3 == 2:
        return None  # Layer III وحده؛ لا تخمين ولا بحث عن تزامن لاحق.
    rates = {3: (44100, 48000, 32000), 2: (22050, 24000, 16000), 0: (11025, 12000, 8000)}
    bits = ((0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320)
            if ver == 3 else (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160))
    return (144 if ver == 3 else 72) * bits[bi] * 1000 // rates[ver][si] + pad


def _tag_end(data, pos):
    h = data[pos:pos + 10]
    if len(h) != 10 or h[:3] != b'ID3' or h[3] not in (3, 4) or h[4] == 255:
        return None
    if h[5] & (31 if h[3] == 3 else 15) or any(x >= 128 for x in h[6:10]):
        return None
    n = (h[6] << 21) | (h[7] << 14) | (h[8] << 7) | h[9]
    end = pos + 10 + n
    if h[3] == 4 and h[5] & 16:
        footer = data[end:end + 10]
        if footer != b'3DI' + h[3:]:
            return None
        end += 10
    return end if end <= len(data) else None


def strip_internal_id3(data):
    """يعيد البايتات الأصلية عند أي إطار ناقص أو حشو غير معروف.

    لا يبحث عن ID3 داخل الحمولة، ولا يعيد التزامن بعد خطأ. النزع لا يتم
    إلا بعد إثبات مسار الملف كله إطاراً بإطار؛ كل بايت صوت يبقى كما كان.
    وTAG النهائي المعروف يبقى أيضاً. وسم الرأس يعالجه المسار القائم.
    """
    if b'ID3' not in data:
        return data
    pos, frames, kept_from, parts = 0, 0, 0, []
    while pos < len(data):
        if len(data) - pos == 128 and data[pos:pos + 3] == b'TAG':
            pos = len(data)
            break
        size = _frame_size(data, pos)
        if size is not None:
            if pos + size > len(data):
                return data
            frames += 1
            pos += size
            continue
        end = _tag_end(data, pos) if frames >= 2 else None
        if end is None or _frame_size(data, end) is None:
            return data
        parts.append(data[kept_from:pos])
        kept_from, pos = end, end
    return b''.join(parts + [data[kept_from:]]) if parts else data

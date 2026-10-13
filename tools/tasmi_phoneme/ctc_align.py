"""محاذٍ CTC بحثي؛ الطوابع لا تثبت صحة النطق ولا تسمح بحكم تجويد.

مدخله احتمالات لوغاريتمية من نموذج صوتي وtoken ids لمرجع موثق.
لا يولد نصاً قرآنياً، ولا يتصل بخدمة، ولا يدخل مسار الحكم في التطبيق.
"""
from dataclasses import dataclass
import math
import numpy as np

@dataclass(frozen=True)
class Span:
    token_index: int
    token_id: int
    start_frame: int
    end_frame: int  # حد حصري
    mean_probability: float


def greedy_decode(log_probs, blank=0):
    x = _validate(log_probs, blank)
    out, previous = [], None
    for value in np.argmax(x, axis=1).tolist():
        if value != blank and value != previous:
            out.append(value)
        previous = value
    return out


def _validate(log_probs, blank):
    x = np.asarray(log_probs, dtype=np.float64)
    if x.ndim != 2 or not x.shape[0] or not x.shape[1]:
        raise ValueError('expected nonempty [frames, vocabulary]')
    if not 0 <= blank < x.shape[1] or np.isnan(x).any() or np.isposinf(x).any():
        raise ValueError('invalid blank or probabilities')
    if np.any(x > 1e-7) or not np.allclose(np.exp(x).sum(axis=1), 1, atol=1e-5):
        raise ValueError('rows must be normalized log probabilities')
    return x


def align(log_probs, target, blank=0, max_cells=5_000_000):
    """Viterbi على حالات CTC، مع فاصل blank إلزامي بين الرموز المتكررة.

    يرجع المقاطع وlog likelihood للمسار؛ يرفض المسار المستحيل ولا يصطنع توقيتاً.
    المقاطع على شبكة النموذج فقط، وليست حدوداً بشرية ولا احتمال صحة التلاوة.
    """
    x = _validate(log_probs, blank)
    target = list(target)
    if not target or any(not isinstance(t, (int, np.integer)) or t == blank or not 0 <= t < x.shape[1] for t in target):
        raise ValueError('target must contain nonblank vocabulary ids')
    frames, _ = x.shape
    minimum = len(target) + sum(a == b for a, b in zip(target, target[1:]))
    if frames < minimum:
        raise ValueError('insufficient frames for target')
    states = [blank]
    for token in target:
        states.extend([token, blank])
    if frames * len(states) > max_cells:
        raise ValueError('alignment exceeds bounded memory budget; segment audio first')
    previous = np.full(len(states), -math.inf)
    previous[:2] = x[0, states[:2]]
    back = np.zeros((frames, len(states)), dtype=np.int8)
    for t in range(1, frames):
        current = np.full(len(states), -math.inf)
        for s, token in enumerate(states):
            candidates = [(previous[s], 0)]
            if s > 0: candidates.append((previous[s-1], 1))
            if s > 1 and token != blank and token != states[s-2]:
                candidates.append((previous[s-2], 2))
            score, step = max(candidates, key=lambda p:p[0])
            current[s] = score + x[t, token]
            back[t, s] = step
        previous = current
    last = max((len(states)-1, len(states)-2), key=lambda s:previous[s])
    score = float(previous[last])
    if not math.isfinite(score):
        raise ValueError('no valid CTC path')
    path = np.zeros(frames, dtype=np.int32)
    for t in range(frames-1, -1, -1):
        path[t] = last
        last -= int(back[t, last])
    spans = []
    for i, token in enumerate(target):
        occupied = np.flatnonzero(path == 2*i+1)
        if not len(occupied): raise ValueError('unvisited target token')
        lo, hi = int(occupied[0]), int(occupied[-1])+1
        spans.append(Span(i, token, lo, hi, float(np.exp(x[occupied, token]).mean())))
    return spans, score

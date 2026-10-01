"""Preserve an original channel when stereo downmix would cancel its speech.

No gain, resampling, or phase synthesis: the exceptional output is channel zero
verbatim. Ordinary stereo and mono retain their existing arithmetic downmix.
"""
import functools
import os
import subprocess

import numpy as np


def cancellation_evidence(x):
    x = np.asarray(x)
    if x.ndim != 2 or x.shape[1] != 2 or len(x) < 1600:
        return None
    if not np.isfinite(x).all():
        return None
    energy = np.mean(x.astype(np.float64) ** 2, axis=0)
    if min(energy) < 1e-6:
        return None
    ratio = float(np.sqrt(energy[0] / energy[1]))
    corr = float(np.mean(x[:, 0].astype(np.float64) * x[:, 1]) /
                 np.sqrt(energy[0] * energy[1]))
    loss = float(np.mean(x.mean(axis=1).astype(np.float64) ** 2) / min(energy))
    # Near-identical opposing channels, with at least 99% power lost on mixing.
    if .9 <= ratio <= 1.1 and corr < -.98 and loss < .01:
        return {'correlation': corr, 'powerRatioAfterMix': loss,
                'channelRms': np.sqrt(energy).tolist(), 'selectedChannel': 0}
    return None


def mono_pcm(x):
    x = np.asarray(x)
    if x.ndim == 1:
        return x
    if cancellation_evidence(x) is not None:
        return x[:, 0]
    return x.mean(axis=1)


@functools.lru_cache(maxsize=256)
def _filter_for_identity(path, size, modified_ns, ffmpeg):
    # This probe decides channel selection only. A failed probe leaves the
    # original decoder path, whose strict error/length/EOF guards still decide.
    try:
        p = subprocess.run([ffmpeg, '-nostdin', '-v', 'error', '-i', path,
                            '-t', '12', '-map', '0:a:0', '-vn', '-ar', '16000',
                            '-ac', '2', '-f', 'f32le', 'pipe:1'],
                           capture_output=True, timeout=30, check=False)
        if p.returncode or p.stderr.strip() or len(p.stdout) % 8:
            return ()
        x = np.frombuffer(p.stdout, dtype='<f4').reshape(-1, 2)
        return ('-af', 'pan=mono|c0=c0') if cancellation_evidence(x) else ()
    except (OSError, subprocess.TimeoutExpired, ValueError):
        return ()


def mono_filter(path, ffmpeg='ffmpeg'):
    try:
        st = os.stat(path)
    except OSError:
        return []
    return list(_filter_for_identity(str(path), st.st_size, st.st_mtime_ns, ffmpeg))

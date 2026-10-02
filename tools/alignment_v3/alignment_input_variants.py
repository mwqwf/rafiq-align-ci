"""Explicit deterministic input spellings; never a shipped Quran text edit.

common.norm is the existing alignment normalization. Small pronounced letters
follow the existing QA spelling map, including its established maqsura rule.
Each measurement records its method; source text and all gates stay unchanged.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / 'alignment'))
from common import norm

METHODS = ('canonical', 'spoken-small-letters', 'common.norm',
           'spoken-small-letters+common.norm')


def alignment_variant(canonical, method='canonical'):
    if method not in METHODS:
        raise ValueError('Unknown deterministic alignment input method')
    text = canonical
    if method.startswith('spoken-small-letters'):
        text = text.replace('ىٰ', 'ى').replace('ٰ', 'ا').replace('ۥ', 'و').replace('ۦ', 'ي')
    if 'common.norm' in method:
        text = norm(text)
    return text

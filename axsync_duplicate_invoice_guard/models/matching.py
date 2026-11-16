# -*- coding: utf-8 -*-
# Part of AXSync. See LICENSE file for full copyright and licensing details.
"""Pure matching rules, independent of the ORM so they are easy to reason about and test."""
import re

from odoo.tools import float_compare

LEVELS = {'low': 1, 'medium': 2, 'high': 3}
LEVEL_NAMES = {1: 'low', 2: 'medium', 3: 'high'}

_NON_ALNUM = re.compile(r'[\W_]+', re.UNICODE)
_ZERO_AFTER_LETTER = re.compile(r'(?<=[^\W\d_])0+(?=\d)', re.UNICODE)


def normalize_reference(value):
    """Reduce a reference to a comparable key.

    Case, spaces, separators and leading zeros are ignored, so 'INV-0001',
    'inv 1' and 'INV/1' give the same key.
    """
    text = _NON_ALNUM.sub('', (value or '').lower())
    text = _ZERO_AFTER_LETTER.sub('', text)
    return text.lstrip('0') or text


def _gap_days(date_a, date_b):
    if not date_a or not date_b:
        return None
    return abs((date_a - date_b).days)


def evaluate_pair(a, b, cfg):
    """Compare two document snapshots.

    :return: None when they do not look alike, otherwise a dict with
             ``reasons`` (list of strings), ``confidence`` and ``level``.
    """
    gap = _gap_days(a['date'], b['date'])
    same_currency = a['currency_id'] == b['currency_id']
    amount_equal = bool(
        same_currency and a['amount'] and b['amount']
        and float_compare(a['amount'], b['amount'], precision_rounding=a['rounding']) == 0)

    ref_window = cfg['reference_days']
    in_ref_window = not ref_window or gap is None or gap <= ref_window
    ref_hit = bool(cfg['match_reference'] and a['ref_key'] and a['ref_key'] == b['ref_key'] and in_ref_window)
    origin_hit = bool(
        cfg['match_origin'] and a['origin_key'] and a['origin_key'] == b['origin_key']
        and amount_equal and in_ref_window)
    amount_hit = bool(cfg['match_amount'] and amount_equal and (gap is None or gap <= cfg['amount_days']))

    reasons = []
    if ref_hit:
        identical = a['ref'].strip().casefold() == b['ref'].strip().casefold()
        reasons.append('Same reference' if identical else 'Similar reference (formatting differs)')
        if amount_equal:
            reasons.append('Same amount')
        level = 3 if amount_equal else 2
    elif origin_hit:
        reasons += ['Same source document', 'Same amount']
        level = 2
    elif amount_hit:
        if gap:
            reasons.append('Same amount, dated %d days apart' % gap)
        else:
            reasons.append('Same amount, same date')
        level = 1
    else:
        return None
    return {'reasons': reasons, 'level': level, 'confidence': LEVEL_NAMES[level]}

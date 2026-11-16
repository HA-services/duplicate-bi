# -*- coding: utf-8 -*-
# Part of AXSync. See LICENSE file for full copyright and licensing details.
from collections import defaultdict
from datetime import timedelta

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.misc import formatLang

from .matching import LEVELS, evaluate_pair, normalize_reference

VENDOR_TYPES = ('in_invoice', 'in_refund')
CUSTOMER_TYPES = ('out_invoice', 'out_refund')
TRACKED_TYPES = VENDOR_TYPES + CUSTOMER_TYPES


class AccountMove(models.Model):
    _inherit = 'account.move'

    axsync_duplicate_ids = fields.Many2many(
        'account.move', string='Possible Duplicates (Duplicate Guard)',
        compute='_compute_axsync_duplicates')
    axsync_duplicate_count = fields.Integer('Possible Duplicates', compute='_compute_axsync_duplicates')
    axsync_duplicate_info = fields.Text('Duplicate Guard Details', compute='_compute_axsync_duplicates')
    axsync_duplicate_blocking = fields.Boolean('Blocked by Duplicate Guard', compute='_compute_axsync_duplicates')

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------
    def _axsync_label(self):
        self.ensure_one()
        name = self.name if self.name and self.name != '/' else False
        if not name:
            name = _('Draft %s', dict(self._fields['move_type'].selection).get(self.move_type, ''))
        return '%s (%s)' % (name, self.ref) if self.ref else name

    def _axsync_snapshot(self):
        self.ensure_one()
        currency = self.currency_id or self.company_id.currency_id
        return {
            'real_id': self._origin.id or 0,
            'partner': self.partner_id.commercial_partner_id.id,
            'ref': self.ref or '',
            'ref_key': normalize_reference(self.ref),
            'origin_key': normalize_reference(self.invoice_origin),
            'amount': currency.round(self.amount_total or 0.0),
            'currency_id': currency.id,
            'rounding': currency.rounding or 0.01,
            'date': self.invoice_date or self.date,
        }

    def _axsync_find_duplicates(self, older_only=False):
        """Look for similar documents.

        One search per company fetches every candidate of all the partners involved,
        the comparison itself is done in memory, so the cost does not grow per record.

        :param older_only: only report documents created before the record. Used by
                           scans so that a pair is reported once, on the newer document.
        :return: ``{record: [{'move', 'reasons', 'confidence', 'level'}, ...]}``
        """
        found = {}
        by_company = defaultdict(lambda: self.browse())
        for move in self:
            if (move.move_type in TRACKED_TYPES and move.state != 'cancel'
                    and move.partner_id.commercial_partner_id):
                by_company[move.company_id] |= move
        for company, records in by_company.items():
            cfg = company._axsync_dup_config()
            if not cfg['enabled']:
                continue
            types = ([*VENDOR_TYPES] if cfg['vendor'] else []) + ([*CUSTOMER_TYPES] if cfg['customer'] else [])
            records = records.filtered(lambda m: m.move_type in types)
            if not records:
                continue
            snaps = {move: move._axsync_snapshot() for move in records}
            candidates = self._axsync_candidates(company, cfg, records, snaps, types)
            index = defaultdict(list)
            for cand in candidates:
                index[(cand.commercial_partner_id.id, cand.move_type)].append(cand)
            cand_snaps = {}
            for move in records:
                snap = snaps[move]
                matches = []
                for cand in index.get((snap['partner'], move.move_type), []):
                    if cand.id == snap['real_id'] or (older_only and cand.id > snap['real_id']):
                        continue
                    if cand not in cand_snaps:
                        cand_snaps[cand] = cand._axsync_snapshot()
                    verdict = evaluate_pair(snap, cand_snaps[cand], cfg)
                    if verdict:
                        verdict['move'] = cand
                        matches.append(verdict)
                if matches:
                    matches.sort(key=lambda m: (-m['level'], m['move'].id))
                    found[move] = matches
        return found

    @api.model
    def _axsync_candidates(self, company, cfg, records, snaps, types):
        states = ['draft', 'posted'] if cfg['drafts'] else ['posted']
        domain = [
            ('company_id', '=', company.id),
            ('move_type', 'in', list({m.move_type for m in records})),
            ('state', 'in', states),
            ('commercial_partner_id', 'in', list({s['partner'] for s in snaps.values()})),
        ]
        windows = []
        if cfg['match_reference'] or cfg['match_origin']:
            windows.append(cfg['reference_days'])
        if cfg['match_amount']:
            windows.append(cfg['amount_days'] + 1)
        if windows and all(windows):
            bound = max(windows)
            dates = [s['date'] for s in snaps.values() if s['date']]
            if dates:
                low, high = min(dates) - timedelta(days=bound), max(dates) + timedelta(days=bound)
                domain += ['|',
                           '&', ('invoice_date', '>=', low), ('invoice_date', '<=', high),
                           '&', ('invoice_date', '=', False), '&', ('date', '>=', low), ('date', '<=', high)]
        return self.env['account.move'].search(domain)

    def _axsync_blocks(self, matches):
        self.ensure_one()
        cfg = self.company_id._axsync_dup_config()
        return bool(
            matches and cfg['enabled'] and cfg['mode'] == 'block'
            and max(m['level'] for m in matches) >= LEVELS[cfg['block_level']])

    def _axsync_describe(self, matches):
        lines = []
        for match in matches:
            other = match['move']
            currency = other.currency_id or other.company_id.currency_id
            lines.append('%s | %s | %s | %s: %s (%s)' % (
                other._axsync_label(),
                dict(other._fields['state'].selection).get(other.state, other.state),
                formatLang(self.env, other.amount_total, currency_obj=currency),
                other.invoice_date or other.date or '',
                ', '.join(match['reasons']),
                match['confidence'],
            ))
        return '\n'.join(lines)

    @api.depends('ref', 'partner_id', 'move_type', 'invoice_date', 'date', 'amount_total', 'currency_id',
                 'invoice_origin', 'state', 'company_id', 'company_id.axsync_dup_enabled',
                 'company_id.axsync_dup_mode', 'company_id.axsync_dup_block_level', 'company_id.axsync_dup_vendor',
                 'company_id.axsync_dup_customer', 'company_id.axsync_dup_match_reference',
                 'company_id.axsync_dup_match_amount', 'company_id.axsync_dup_match_origin',
                 'company_id.axsync_dup_reference_days', 'company_id.axsync_dup_amount_days',
                 'company_id.axsync_dup_include_drafts')
    def _compute_axsync_duplicates(self):
        found = self._axsync_find_duplicates()
        for move in self:
            matches = found.get(move, [])
            move.axsync_duplicate_ids = [m['move'].id for m in matches]
            move.axsync_duplicate_count = len(matches)
            move.axsync_duplicate_info = move._axsync_describe(matches) if matches else False
            move.axsync_duplicate_blocking = bool(
                matches and move.state == 'draft' and move._axsync_blocks(matches))

    # ------------------------------------------------------------------
    # Posting
    # ------------------------------------------------------------------
    def action_post(self):
        found = {}
        if not self.env.context.get('axsync_skip_duplicate_check'):
            found = self._axsync_guard_before_post()
        result = super().action_post()
        if found:
            self._axsync_log_matches(found, 'post')
        return result

    def _axsync_guard_before_post(self):
        drafts = self.filtered(lambda m: m.move_type in TRACKED_TYPES and m.state == 'draft')
        found = drafts._axsync_find_duplicates()
        blocked = [(move, matches) for move, matches in found.items() if move._axsync_blocks(matches)]
        if blocked:
            parts = [_('Duplicate Guard stopped this posting. These documents look like duplicates:')]
            for move, matches in blocked:
                parts.append('\n%s' % move._axsync_label())
                parts.append(move._axsync_describe(matches))
            parts.append(_('\nReview them. If the document is genuine, ask an accounting manager to use '
                           '"Post Anyway" and record the reason. Otherwise delete or cancel the duplicate.'))
            raise UserError('\n'.join(parts))
        return found

    def _axsync_log_matches(self, found, source, state='open', note=False):
        Case = self.env['axsync.duplicate.case']
        for move, matches in found.items():
            case, created = Case._axsync_register(move, matches, source, state=state, note=note)
            if created and case:
                move.message_post(body=Markup(_('Duplicate Guard: possible duplicate of %s.')) % ', '.join(
                    m['move']._axsync_label() for m in matches[:5]))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_axsync_view_duplicates(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Possible Duplicates'),
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.axsync_duplicate_ids.ids)],
            'context': {'create': False},
        }

    def action_axsync_post_anyway(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Post Anyway'),
            'res_model': 'axsync.duplicate.override.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_move_ids': self.ids},
        }

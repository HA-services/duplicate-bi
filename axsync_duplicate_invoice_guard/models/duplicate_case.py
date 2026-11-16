# -*- coding: utf-8 -*-
# Part of AXSync. See LICENSE file for full copyright and licensing details.
from datetime import timedelta

from psycopg2 import IntegrityError

from odoo import _, api, fields, models

from .account_move import CUSTOMER_TYPES, VENDOR_TYPES


class DuplicateCase(models.Model):
    _name = 'axsync.duplicate.case'
    _description = 'Duplicate Invoice Case'
    _order = 'id desc'

    name = fields.Char(compute='_compute_name', store=True)
    move_id = fields.Many2one('account.move', string='Document', required=True, index=True, ondelete='cascade')
    matched_move_ids = fields.Many2many(
        'account.move', 'axsync_duplicate_case_move_rel', 'case_id', 'move_id', string='Looks Like')
    matched_count = fields.Integer(compute='_compute_matched_count')
    match_key = fields.Char(required=True, index=True)
    confidence = fields.Selection(
        [('low', 'Low'), ('medium', 'Medium'), ('high', 'High')], required=True, default='medium')
    reasons = fields.Char()
    source = fields.Selection(
        [('post', 'Posting'), ('scan', 'Scan'), ('override', 'Posted anyway')], default='scan', required=True)
    state = fields.Selection(
        [('open', 'To Review'), ('dismissed', 'Not a Duplicate'), ('duplicate', 'Confirmed Duplicate'),
         ('overridden', 'Posted Anyway')], default='open', required=True, index=True)
    note = fields.Text('Reason / Note')
    resolved_by = fields.Many2one('res.users', readonly=True)
    resolved_date = fields.Datetime(readonly=True)

    company_id = fields.Many2one(related='move_id.company_id', store=True, index=True)
    company_currency_id = fields.Many2one(related='company_id.currency_id')
    partner_id = fields.Many2one(related='move_id.commercial_partner_id', store=True, index=True, string='Partner')
    move_type = fields.Selection(related='move_id.move_type', store=True, string='Type')
    move_state = fields.Selection(related='move_id.state', string='Document Status')
    invoice_date = fields.Date(related='move_id.invoice_date', store=True)
    ref = fields.Char(related='move_id.ref', string='Reference')
    amount_company = fields.Monetary(
        'Amount', compute='_compute_amount_company', store=True, currency_field='company_currency_id')

    _sql_constraints = [
        ('move_key_unique', 'unique(move_id, match_key)', 'This duplicate case already exists.'),
    ]

    @api.depends('move_id.name', 'move_id.ref')
    def _compute_name(self):
        for case in self:
            case.name = case.move_id._axsync_label() if case.move_id else _('Case')

    @api.depends('matched_move_ids')
    def _compute_matched_count(self):
        for case in self:
            case.matched_count = len(case.matched_move_ids)

    @api.depends('move_id.amount_total_signed')
    def _compute_amount_company(self):
        for case in self:
            case.amount_company = abs(case.move_id.amount_total_signed or 0.0)

    # ------------------------------------------------------------------
    # Registering and resolving
    # ------------------------------------------------------------------
    @api.model
    def _axsync_register(self, move, matches, source, state='open', note=False):
        """Create the case of ``move`` once per set of matching documents.

        :return: ``(case, created)``
        """
        ids = sorted({m['move'].id for m in matches if m['move'].id})
        if not move.id or not ids:
            return self.browse(), False
        key = ','.join(str(i) for i in ids)
        case = self.search([('move_id', '=', move.id), ('match_key', '=', key)], limit=1)
        created = False
        if not case:
            best = max(matches, key=lambda m: m['level'])
            reasons = []
            for match in matches:
                for reason in match['reasons']:
                    if reason not in reasons:
                        reasons.append(reason)
            vals = {
                'move_id': move.id,
                'match_key': key,
                'matched_move_ids': [(6, 0, ids)],
                'confidence': best['confidence'],
                'reasons': '; '.join(reasons)[:250],
                'source': source,
            }
            try:
                with self.env.cr.savepoint():
                    case = self.create(vals)
                created = True
            except IntegrityError:
                case = self.search([('move_id', '=', move.id), ('match_key', '=', key)], limit=1)
        if state != 'open' and case.state != state:
            case._axsync_resolve(state, note)
        return case, created

    def _axsync_resolve(self, resolution, note=False):
        vals = {'state': resolution, 'resolved_by': self.env.user.id, 'resolved_date': fields.Datetime.now()}
        if note:
            vals['note'] = note
        self.write(vals)

    def action_reopen(self):
        self.write({'state': 'open', 'resolved_by': False, 'resolved_date': False})

    def action_open_move(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'res_model': 'account.move', 'res_id': self.move_id.id,
            'view_mode': 'form', 'views': [(False, 'form')],
        }

    def action_view_matches(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Looks Like'), 'res_model': 'account.move',
            'view_mode': 'list,form', 'domain': [('id', 'in', self.matched_move_ids.ids)],
            'context': {'create': False},
        }

    # ------------------------------------------------------------------
    # Scan
    # ------------------------------------------------------------------
    @api.model
    def _axsync_scan(self, date_from=None, date_to=None, companies=None):
        """Create cases for existing documents. Returns the number of new cases."""
        Move = self.env['account.move']
        companies = companies if companies is not None else self.env['res.company'].search([])
        created = 0
        today = fields.Date.context_today(self)
        for company in companies:
            cfg = company._axsync_dup_config()
            types = ([*VENDOR_TYPES] if cfg['vendor'] else []) + ([*CUSTOMER_TYPES] if cfg['customer'] else [])
            if not cfg['enabled'] or not types:
                continue
            end = date_to or today
            start = date_from or (end - timedelta(days=company.axsync_dup_scan_days))
            domain = [
                ('company_id', '=', company.id), ('move_type', 'in', types), ('state', 'in', ('draft', 'posted')),
                '|', '&', ('invoice_date', '>=', start), ('invoice_date', '<=', end),
                '&', ('invoice_date', '=', False), '&', ('date', '>=', start), ('date', '<=', end),
            ]
            moves = Move.with_company(company).search(domain, order='id')
            for index in range(0, len(moves), 200):
                batch = moves[index:index + 200]
                for move, matches in batch._axsync_find_duplicates(older_only=True).items():
                    created += self._axsync_register(move, matches, 'scan')[1]
        return created

    @api.model
    def _axsync_refresh_open(self, companies=None):
        """Close open cases that no longer make sense (cancelled or no match left)."""
        domain = [('state', '=', 'open')]
        if companies is not None:
            domain.append(('company_id', 'in', companies.ids))
        cases = self.search(domain)
        cancelled = cases.filtered(lambda c: c.move_id.state == 'cancel')
        cancelled._axsync_resolve('duplicate', _('The document was cancelled.'))
        remaining = cases - cancelled
        found = remaining.mapped('move_id')._axsync_find_duplicates()
        for case in remaining:
            if case.move_id not in found:
                case._axsync_resolve('dismissed', _('No longer matches any other document.'))

    @api.model
    def cron_scan_duplicates(self):
        # System job: it looks at every company that opted in, whatever the user running it can access.
        self = self.sudo()
        companies = self.env['res.company'].search(
            [('axsync_dup_enabled', '=', True), ('axsync_dup_auto_scan', '=', True)])
        created = self._axsync_scan(companies=companies)
        self._axsync_refresh_open(companies)
        return created

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    @api.model
    def _aggregate(self, domain, fname, op='sum'):
        res = self._read_group(domain, [], ['%s:%s' % (fname, op)])
        return (res[0][0] or 0.0) if res else 0.0

    @api.model
    def _partner_breakdown(self, domain, limit=8):
        groups = self._read_group(
            domain, ['partner_id'], ['__count', 'amount_company:sum'], order='__count desc', limit=limit)
        return [{
            'id': partner.id, 'partner': partner.display_name,
            'cases': count, 'amount': round(total or 0.0, 2),
        } for partner, count, total in groups if partner]

    @api.model
    def get_dashboard_data(self, days=90):
        days = int(days or 0)
        company = self.env.company
        symbol = company.currency_id.symbol or ''
        base = [('company_id', '=', company.id)]
        since = fields.Datetime.now() - timedelta(days=days) if days else False
        in_period = [('resolved_date', '>=', since)] if since else []
        label = 'Last %d days' % days if days else 'All time'
        model = 'axsync.duplicate.case'
        open_dom = base + [('state', '=', 'open')]
        high_dom = open_dom + [('confidence', '=', 'high')]
        dup_dom = base + [('state', '=', 'duplicate')] + in_period
        over_dom = base + [('state', '=', 'overridden')] + in_period
        dis_dom = base + [('state', '=', 'dismissed')] + in_period
        confirmed = self.search_count(dup_dom)
        dismissed = self.search_count(dis_dom)
        tiles = [
            {'key': 'open', 'label': 'Cases to review', 'sub': 'Live', 'tone': 'danger',
             'value': self.search_count(open_dom), 'model': model, 'domain': open_dom},
            {'key': 'risk', 'label': 'Amount under review', 'sub': 'Live', 'tone': 'warning',
             'value': round(self._aggregate(open_dom, 'amount_company'), 2), 'prefix': symbol + ' ',
             'model': model, 'domain': open_dom},
            {'key': 'high', 'label': 'High confidence', 'sub': 'Live', 'tone': 'danger',
             'value': self.search_count(high_dom), 'model': model, 'domain': high_dom},
            {'key': 'confirmed', 'label': 'Duplicates confirmed', 'sub': label, 'tone': 'success',
             'value': confirmed, 'model': model, 'domain': dup_dom},
            {'key': 'confirmed_amount', 'label': 'Value of confirmed duplicates', 'sub': label, 'tone': 'success',
             'value': round(self._aggregate(dup_dom, 'amount_company'), 2), 'prefix': symbol + ' ',
             'model': model, 'domain': dup_dom},
            {'key': 'overridden', 'label': 'Posted anyway', 'sub': label, 'tone': 'info',
             'value': self.search_count(over_dom), 'model': model, 'domain': over_dom},
            {'key': 'dismissed', 'label': 'Marked not a duplicate', 'sub': label, 'tone': 'secondary',
             'value': dismissed, 'model': model, 'domain': dis_dom},
            {'key': 'rate', 'label': 'Confirmation rate', 'sub': label, 'tone': 'primary',
             'value': round(confirmed * 100.0 / (confirmed + dismissed), 1) if (confirmed + dismissed) else 0.0,
             'suffix': ' %', 'model': model, 'domain': dup_dom + [('state', 'in', ('duplicate', 'dismissed'))]},
        ]
        today = fields.Date.context_today(self)
        oldest = []
        for case in self.search(open_dom, order='create_date asc, id', limit=8):
            created = fields.Datetime.context_timestamp(self, case.create_date).date()
            oldest.append({
                'id': case.id, 'name': case.name, 'partner': case.partner_id.display_name or '',
                'amount': round(case.amount_company, 2), 'confidence': case.confidence,
                'age': max((today - created).days, 0),
            })
        return {
            'tiles': tiles,
            'oldest': oldest,
            'partners': self._partner_breakdown(base + [('state', 'in', ('open', 'duplicate'))]),
            'symbol': symbol,
        }

    # ------------------------------------------------------------------
    # Resolution buttons
    # ------------------------------------------------------------------
    def _axsync_open_resolve(self, resolution):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Resolve Cases'),
            'res_model': 'axsync.duplicate.resolve.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_case_ids': [(6, 0, self.ids)], 'default_resolution': resolution},
        }

    def action_dismiss(self):
        return self._axsync_open_resolve('dismissed')

    def action_confirm_duplicate(self):
        return self._axsync_open_resolve('duplicate')

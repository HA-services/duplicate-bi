# -*- coding: utf-8 -*-
# Part of AXSync. See LICENSE file for full copyright and licensing details.
from datetime import timedelta

from odoo import _, api, fields, models


class DuplicateScanWizard(models.TransientModel):
    _name = 'axsync.duplicate.scan.wizard'
    _description = 'Scan for Duplicates'

    date_from = fields.Date('From', required=True)
    date_to = fields.Date('To', required=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        today = fields.Date.context_today(self)
        res.setdefault('date_to', today)
        res.setdefault('date_from', today - timedelta(days=self.env.company.axsync_dup_scan_days or 30))
        return res

    def action_scan(self):
        self.ensure_one()
        Case = self.env['axsync.duplicate.case']
        created = Case._axsync_scan(self.date_from, self.date_to, companies=self.env.companies)
        Case._axsync_refresh_open(self.env.companies)
        action = self.env['ir.actions.actions']._for_xml_id(
            'axsync_duplicate_invoice_guard.axsync_duplicate_case_review_action')
        action['name'] = _('Review Queue (%s new)', created)
        return action

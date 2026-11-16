# -*- coding: utf-8 -*-
# Part of AXSync. See LICENSE file for full copyright and licensing details.
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = 'res.company'

    axsync_dup_enabled = fields.Boolean('Duplicate Guard', default=True)
    axsync_dup_mode = fields.Selection(
        [('warn', 'Warn only'), ('block', 'Block posting')], string='When a duplicate is found',
        default='warn', required=True)
    axsync_dup_block_level = fields.Selection(
        [('high', 'High confidence only'), ('medium', 'Medium confidence or higher'), ('low', 'Any match')],
        string='Block from', default='medium', required=True)
    axsync_dup_vendor = fields.Boolean('Check Vendor Bills', default=True)
    axsync_dup_customer = fields.Boolean('Check Customer Invoices', default=True)
    axsync_dup_match_reference = fields.Boolean('Match on Reference', default=True)
    axsync_dup_match_amount = fields.Boolean('Match on Amount and Date', default=True)
    axsync_dup_match_origin = fields.Boolean('Match on Source Document', default=True)
    axsync_dup_reference_days = fields.Integer(
        'Reference Window (Days)', default=365,
        help='Only compare documents dated within this many days of each other. 0 means no limit.')
    axsync_dup_amount_days = fields.Integer(
        'Amount Window (Days)', default=7,
        help='Documents with the same amount are flagged when dated within this many days of each other.')
    axsync_dup_include_drafts = fields.Boolean('Compare with Drafts', default=True)
    axsync_dup_auto_scan = fields.Boolean('Daily Scan', default=True)
    axsync_dup_scan_days = fields.Integer('Scan Look-back (Days)', default=30)

    @api.constrains('axsync_dup_reference_days', 'axsync_dup_amount_days', 'axsync_dup_scan_days')
    def _check_axsync_dup_days(self):
        for company in self:
            if min(company.axsync_dup_reference_days, company.axsync_dup_amount_days,
                   company.axsync_dup_scan_days) < 0:
                raise ValidationError(_('Duplicate Guard day limits cannot be negative.'))

    def _axsync_dup_config(self):
        self.ensure_one()
        return {
            'enabled': self.axsync_dup_enabled,
            'mode': self.axsync_dup_mode,
            'block_level': self.axsync_dup_block_level,
            'vendor': self.axsync_dup_vendor,
            'customer': self.axsync_dup_customer,
            'match_reference': self.axsync_dup_match_reference,
            'match_amount': self.axsync_dup_match_amount,
            'match_origin': self.axsync_dup_match_origin,
            'reference_days': self.axsync_dup_reference_days,
            'amount_days': self.axsync_dup_amount_days,
            'drafts': self.axsync_dup_include_drafts,
        }

# -*- coding: utf-8 -*-
# Part of AXSync. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    axsync_dup_enabled = fields.Boolean(related='company_id.axsync_dup_enabled', readonly=False)
    axsync_dup_mode = fields.Selection(related='company_id.axsync_dup_mode', readonly=False)
    axsync_dup_block_level = fields.Selection(related='company_id.axsync_dup_block_level', readonly=False)
    axsync_dup_vendor = fields.Boolean(related='company_id.axsync_dup_vendor', readonly=False)
    axsync_dup_customer = fields.Boolean(related='company_id.axsync_dup_customer', readonly=False)
    axsync_dup_match_reference = fields.Boolean(related='company_id.axsync_dup_match_reference', readonly=False)
    axsync_dup_match_amount = fields.Boolean(related='company_id.axsync_dup_match_amount', readonly=False)
    axsync_dup_match_origin = fields.Boolean(related='company_id.axsync_dup_match_origin', readonly=False)
    axsync_dup_reference_days = fields.Integer(related='company_id.axsync_dup_reference_days', readonly=False)
    axsync_dup_amount_days = fields.Integer(related='company_id.axsync_dup_amount_days', readonly=False)
    axsync_dup_include_drafts = fields.Boolean(related='company_id.axsync_dup_include_drafts', readonly=False)
    axsync_dup_auto_scan = fields.Boolean(related='company_id.axsync_dup_auto_scan', readonly=False)
    axsync_dup_scan_days = fields.Integer(related='company_id.axsync_dup_scan_days', readonly=False)

    def action_axsync_scan_now(self):
        self.execute()
        return self.env['ir.actions.actions']._for_xml_id('axsync_duplicate_invoice_guard.axsync_duplicate_scan_wizard_action')

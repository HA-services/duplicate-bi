# -*- coding: utf-8 -*-
# Part of AXSync. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class DuplicateResolveWizard(models.TransientModel):
    _name = 'axsync.duplicate.resolve.wizard'
    _description = 'Resolve Duplicate Cases'

    case_ids = fields.Many2many('axsync.duplicate.case', string='Cases')
    resolution = fields.Selection(
        [('dismissed', 'Not a duplicate'), ('duplicate', 'Confirmed duplicate')], required=True, default='dismissed')
    note = fields.Text('Note')

    def action_confirm(self):
        self.ensure_one()
        self.case_ids.filtered(lambda c: c.state == 'open')._axsync_resolve(self.resolution, self.note)
        return {'type': 'ir.actions.act_window_close'}

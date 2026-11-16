# -*- coding: utf-8 -*-
# Part of AXSync. See LICENSE file for full copyright and licensing details.
from markupsafe import Markup

from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError


class DuplicateOverrideWizard(models.TransientModel):
    _name = 'axsync.duplicate.override.wizard'
    _description = 'Post a Possible Duplicate Anyway'

    move_ids = fields.Many2many('account.move', string='Documents')
    note = fields.Text('Reason', required=True, help='Why is this document not a duplicate? It is kept in the audit log.')
    summary = fields.Text(compute='_compute_summary')

    def _compute_summary(self):
        for wizard in self:
            found = wizard.move_ids._axsync_find_duplicates()
            parts = []
            for move, matches in found.items():
                parts.append('%s\n%s' % (move._axsync_label(), move._axsync_describe(matches)))
            wizard.summary = '\n\n'.join(parts) or _('No duplicate found any more.')

    def action_confirm(self):
        self.ensure_one()
        if not self.env.user.has_group('account.group_account_manager'):
            raise AccessError(_('Only accounting managers can post a document flagged as a possible duplicate.'))
        moves = self.move_ids.filtered(lambda m: m.state == 'draft')
        if not moves:
            raise UserError(_('There is no draft document to post.'))
        found = moves._axsync_find_duplicates()
        moves._axsync_log_matches(found, 'override', state='overridden', note=self.note)
        for move in found:
            move.message_post(body=Markup(_('Duplicate Guard: posted anyway. Reason: %s')) % self.note)
        moves.with_context(axsync_skip_duplicate_check=True).action_post()
        return {'type': 'ir.actions.act_window_close'}

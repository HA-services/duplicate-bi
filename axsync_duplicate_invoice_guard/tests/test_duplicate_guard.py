# -*- coding: utf-8 -*-
# Part of AXSync. See LICENSE file for full copyright and licensing details.
from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import Form, tagged
from odoo.tests.common import new_test_user

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

# Version specific names, adapted when the module is ported.
LIST = 'list'


@tagged('post_install', '-at_install', 'axsync_dup')
class TestDuplicateGuard(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data['company']
        cls.today = fields.Date.context_today(cls.env['res.partner'])
        cls.Case = cls.env['axsync.duplicate.case']
        cls.billing = new_test_user(
            cls.env, login='axdup_billing', groups='account.group_account_invoice', company_id=cls.company.id)
        cls.manager = new_test_user(
            cls.env, login='axdup_manager', groups='account.group_account_manager', company_id=cls.company.id)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _day(self, offset=0):
        return self.today + timedelta(days=offset)

    def _inv(self, move_type='in_invoice', partner=None, ref=None, amount=100.0, offset=0, origin=None,
             company=None, post=False, currency=None):
        company = company or self.company
        vals = {
            'move_type': move_type,
            'partner_id': (partner or self.partner_a).id,
            'invoice_date': self._day(offset),
            'date': self._day(offset),
            'ref': ref,
            'invoice_origin': origin,
            'company_id': company.id,
            'invoice_line_ids': [Command.create({'name': 'line', 'quantity': 1, 'price_unit': amount})],
        }
        if currency:
            vals['currency_id'] = currency.id
        move = self.env['account.move'].with_company(company).with_context(
            default_move_type=move_type).create(vals)
        if post:
            move.with_context(axsync_skip_duplicate_check=True).action_post()
        # computed fields are cached per transaction, a screen reads them fresh
        self.env.invalidate_all()
        return move

    def _set(self, **vals):
        self.company.write({'axsync_dup_' + key: value for key, value in vals.items()})
        self.env.invalidate_all()

    def _case_for(self, move):
        return self.Case.search([('move_id', '=', move.id)])

    # ------------------------------------------------------------------
    # 01 installation
    # ------------------------------------------------------------------
    def test_01_install_views_cron_defaults(self):
        self.assertTrue(self.env.ref('axsync_duplicate_invoice_guard.axsync_duplicate_scan_cron').active)
        self.assertTrue(self.company.axsync_dup_enabled)
        self.assertEqual(self.company.axsync_dup_mode, 'warn')
        self.assertEqual(self.company.axsync_dup_block_level, 'medium')
        views = [(False, LIST), (False, 'form'), (False, 'search'), (False, 'pivot'), (False, 'graph')]
        result = self.Case.get_views(views)
        self.assertEqual(set(result['views']), {LIST, 'form', 'search', 'pivot', 'graph'})
        move_form = self.env['account.move'].get_view(self.env.ref('account.view_move_form').id, 'form')
        self.assertIn('axsync_duplicate_count', move_form['arch'])
        from lxml import etree
        banners = etree.fromstring(move_form['arch']).xpath("//div[contains(@invisible, 'duplicate')]")
        self.assertTrue(banners)
        for banner in banners:
            self.assertIn('axsync_duplicate_count', banner.get('invisible'))
        settings = self.env['res.config.settings'].get_view(
            self.env.ref('account.res_config_settings_view_form').id, 'form')
        self.assertIn('axsync_dup_mode', settings['arch'])
        for wizard in ('axsync.duplicate.resolve.wizard', 'axsync.duplicate.override.wizard',
                       'axsync.duplicate.scan.wizard'):
            self.assertIn('form', self.env[wizard].get_views([(False, 'form')])['views'])
        self.assertIn('axsync_duplicate_dashboard', self.env.ref(
            'axsync_duplicate_invoice_guard.axsync_duplicate_dashboard_action').tag)

    # ------------------------------------------------------------------
    # 02 / 03 reference rules
    # ------------------------------------------------------------------
    def test_02_same_reference_and_amount_is_high(self):
        original = self._inv(ref='BILL-77', amount=250.0, post=True)
        dup = self._inv(ref='BILL-77', amount=250.0)
        self.assertEqual(dup.axsync_duplicate_ids, original)
        self.assertEqual(dup.axsync_duplicate_count, 1)
        self.assertIn('Same reference', dup.axsync_duplicate_info)
        self.assertIn('Same amount', dup.axsync_duplicate_info)
        self.assertIn('(high)', dup.axsync_duplicate_info)
        # both directions are visible on forms
        self.assertEqual(original.axsync_duplicate_ids, dup)
        found = dup._axsync_find_duplicates()
        self.assertEqual(found[dup][0]['confidence'], 'high')

    def test_03_reference_formats_and_negatives(self):
        original = self._inv(ref='INV-0001', amount=100.0, post=True)
        for index, variant in enumerate(('inv 1', 'INV/001', 'Inv.1', ' inv-1 ')):
            dup = self._inv(ref=variant, amount=900.0 + index, offset=2)
            self.assertEqual(dup.axsync_duplicate_ids & original, original, variant)
            self.assertIn('Similar reference', dup.axsync_duplicate_info)
            found = dup._axsync_find_duplicates()
            self.assertEqual(found[dup][0]['confidence'], 'medium')
        self.assertFalse(self._inv(ref='INV-10', amount=999.0, offset=2).axsync_duplicate_ids)
        self.assertFalse(self._inv(ref='INV-0001', partner=self.partner_b, offset=2).axsync_duplicate_ids)
        refund = self._inv(move_type='in_refund', ref='INV-0001', amount=100.0, offset=2)
        self.assertFalse(refund.axsync_duplicate_ids)
        self.assertFalse(self._inv(ref=False, amount=777.0, offset=2).axsync_duplicate_ids)
        # outside the reference window
        self._set(reference_days=30)
        far = self._inv(ref='INV-0001', amount=555.0, offset=90)
        self.assertFalse(far.axsync_duplicate_ids, far.axsync_duplicate_info)
        self.assertTrue(self._inv(ref='INV-0001', amount=999.0, offset=20).axsync_duplicate_ids)

    # ------------------------------------------------------------------
    # 04 amount rule
    # ------------------------------------------------------------------
    def test_04_amount_within_window(self):
        original = self._inv(ref='A-1', amount=480.0, post=True)
        near = self._inv(ref='B-2', amount=480.0, offset=3)
        self.assertEqual(near.axsync_duplicate_ids, original)
        self.assertEqual(near._axsync_find_duplicates()[near][0]['confidence'], 'low')
        self.assertIn('dated 3 days apart', near.axsync_duplicate_info)
        self.assertFalse(self._inv(ref='C-3', amount=480.0, offset=20).axsync_duplicate_ids)
        self.assertFalse(self._inv(ref='D-4', amount=481.0, offset=1).axsync_duplicate_ids)
        self._set(amount_days=0)
        self.assertFalse(near.axsync_duplicate_ids)
        same_day = self._inv(ref='E-5', amount=480.0)
        self.assertIn('same date', same_day.axsync_duplicate_info)
        self._set(match_amount=False)
        self.assertFalse(same_day.axsync_duplicate_ids)

    def test_05_other_currency_is_not_compared(self):
        eur = self.env.ref('base.EUR')
        eur.active = True
        self._inv(ref='C-1', amount=300.0, post=True)
        self.assertFalse(self._inv(ref='C-2', amount=300.0, currency=eur).axsync_duplicate_ids)

    # ------------------------------------------------------------------
    # 06 source document and customer invoices
    # ------------------------------------------------------------------
    def test_06_source_document_and_customers(self):
        first = self._inv('out_invoice', ref=False, amount=900.0, origin='SO0042', offset=-60, post=True)
        second = self._inv('out_invoice', ref=False, amount=900.0, origin='so-0042', offset=0)
        self.assertEqual(second.axsync_duplicate_ids, first)
        self.assertEqual(second._axsync_find_duplicates()[second][0]['confidence'], 'medium')
        self.assertIn('Same source document', second.axsync_duplicate_info)
        self.assertFalse(self._inv('out_invoice', amount=901.0, origin='SO0042', offset=0).axsync_duplicate_ids)
        by_ref = self._inv('out_invoice', ref='PO-9', amount=50.0, offset=-40, post=True)
        self.assertEqual(self._inv('out_invoice', ref='PO-9', amount=50.0).axsync_duplicate_ids, by_ref)
        same_day = self._inv('out_invoice', partner=self.partner_b, amount=70.0, post=True)
        self.assertEqual(self._inv('out_invoice', partner=self.partner_b, amount=70.0).axsync_duplicate_ids, same_day)
        self._set(match_origin=False)
        self.assertFalse(second.axsync_duplicate_ids)
        self._set(customer=False)
        self.assertFalse(self._inv('out_invoice', ref='PO-9', amount=50.0).axsync_duplicate_ids)
        vendor = self._inv(ref='V-1', amount=33.0, post=True)
        self.assertEqual(self._inv(ref='V-1', amount=33.0).axsync_duplicate_ids, vendor)
        self._set(vendor=False)
        self.assertFalse(self._inv(ref='V-1', amount=33.0).axsync_duplicate_ids)

    def test_07_cancelled_drafts_and_disabled(self):
        draft = self._inv(ref='D-1', amount=60.0)
        other = self._inv(ref='D-1', amount=60.0)
        self.assertEqual(other.axsync_duplicate_ids, draft)
        self._set(include_drafts=False)
        self.assertFalse(other.axsync_duplicate_ids)
        self._set(include_drafts=True)
        draft.button_cancel()
        self.env.invalidate_all()
        self.assertFalse(other.axsync_duplicate_ids)
        self.assertFalse(draft.axsync_duplicate_ids)
        posted = self._inv(ref='D-2', amount=60.0, post=True)
        dup = self._inv(ref='D-2', amount=60.0)
        self.assertTrue(dup.axsync_duplicate_ids)
        self._set(enabled=False)
        self.assertFalse(dup.axsync_duplicate_ids)
        self.assertTrue(posted)
        entry = self.env['account.move'].create({'move_type': 'entry', 'ref': 'D-2'})
        self.assertFalse(entry.axsync_duplicate_ids)

    # ------------------------------------------------------------------
    # 08 posting
    # ------------------------------------------------------------------
    def test_08_warn_mode_posts_and_logs_once(self):
        original = self._inv(ref='W-1', amount=120.0, post=True)
        dup = self._inv(ref='W-1', amount=120.0)
        messages = len(dup.message_ids)
        dup.action_post()
        self.assertEqual(dup.state, 'posted')
        case = self._case_for(dup)
        self.assertEqual(len(case), 1)
        self.assertEqual((case.state, case.source, case.confidence), ('open', 'post', 'high'))
        self.assertEqual(case.matched_move_ids, original)
        self.assertGreater(len(dup.message_ids), messages)
        self.assertEqual(case.partner_id, self.partner_a)
        self.assertEqual(case.amount_company, 120.0)

    def test_09_block_mode(self):
        self._set(mode='block')
        original = self._inv(ref='B-1', amount=500.0, post=True)
        dup = self._inv(ref='B-1', amount=500.0)
        self.assertTrue(dup.axsync_duplicate_blocking)
        with self.assertRaises(UserError) as caught:
            dup.action_post()
        self.assertIn('Duplicate Guard', str(caught.exception))
        self.assertIn('B-1', str(caught.exception))
        self.assertEqual(dup.state, 'draft')
        clean = self._inv(ref='B-2', amount=10.0, partner=self.partner_b)
        clean.action_post()
        self.assertEqual(clean.state, 'posted')
        # one blocked record stops the whole batch
        clean2 = self._inv(ref='B-3', amount=11.0, partner=self.partner_b)
        with self.assertRaises(UserError):
            (clean2 + dup).action_post()
        self.assertEqual((clean2 + dup).mapped('state'), ['draft', 'draft'])
        # low confidence is not blocked at the default level
        self._inv(ref='X-1', amount=75.0, post=True)
        low = self._inv(ref='X-2', amount=75.0, offset=1)
        self.assertEqual(low._axsync_find_duplicates()[low][0]['confidence'], 'low')
        self.assertFalse(low.axsync_duplicate_blocking)
        low.action_post()
        self.assertEqual(low.state, 'posted')
        self._set(block_level='low')
        low2 = self._inv(ref='X-3', amount=75.0, offset=1)
        self.assertTrue(low2.axsync_duplicate_blocking)
        with self.assertRaises(UserError):
            low2.action_post()
        self._set(block_level='high')
        ref_only = self._inv(ref='B-1', amount=501.0)
        self.assertFalse(ref_only.axsync_duplicate_blocking)
        self._set(block_level='medium')
        self.assertTrue(ref_only.axsync_duplicate_blocking)
        # programmatic bypass
        dup.with_context(axsync_skip_duplicate_check=True).action_post()
        self.assertEqual(dup.state, 'posted')
        self.assertTrue(original)

    def test_10_customer_invoice_blocked_and_entries_untouched(self):
        self._set(mode='block')
        self._inv('out_invoice', partner=self.partner_b, amount=40.0, ref='CI-1', post=True)
        dup = self._inv('out_invoice', partner=self.partner_b, amount=40.0, ref='CI-1')
        with self.assertRaises(UserError):
            dup.action_post()
        entry = self.env['account.move'].create({
            'move_type': 'entry', 'ref': 'CI-1', 'journal_id': self.company_data['default_journal_misc'].id,
            'line_ids': [
                Command.create({'account_id': self.company_data['default_account_receivable'].id, 'debit': 5.0}),
                Command.create({'account_id': self.company_data['default_account_revenue'].id, 'credit': 5.0}),
            ]})
        entry.action_post()
        self.assertEqual(entry.state, 'posted')

    # ------------------------------------------------------------------
    # 11 override
    # ------------------------------------------------------------------
    def test_11_override_requires_manager_and_reason(self):
        self._set(mode='block')
        self._inv(ref='O-1', amount=300.0, post=True)
        dup = self._inv(ref='O-1', amount=300.0)
        with self.assertRaises(UserError):
            dup.with_user(self.billing).action_post()
        action = dup.action_axsync_post_anyway()
        self.assertEqual(action['res_model'], 'axsync.duplicate.override.wizard')
        with self.assertRaises(AccessError):
            self.env['axsync.duplicate.override.wizard'].with_user(self.billing).create(
                {'move_ids': [Command.set(dup.ids)], 'note': 'second delivery'})
        self.assertEqual(dup.state, 'draft')
        wizard = self.env['axsync.duplicate.override.wizard'].with_user(self.manager).create(
            {'move_ids': [Command.set(dup.ids)], 'note': 'Supplier reused the number for a second delivery'})
        self.assertIn('O-1', wizard.summary)
        wizard.action_confirm()
        self.assertEqual(dup.state, 'posted')
        case = self._case_for(dup)
        self.assertEqual(case.state, 'overridden')
        self.assertEqual(case.resolved_by, self.manager)
        self.assertIn('second delivery', case.note)
        self.assertTrue(case.resolved_date)
        self.assertTrue(any('posted anyway' in (m.body or '') for m in dup.message_ids))

    # ------------------------------------------------------------------
    # 12 scan, cron and review
    # ------------------------------------------------------------------
    def test_12_scan_is_idempotent_and_reports_newer_document(self):
        first = self._inv(ref='S-1', amount=20.0, post=True)
        second = self._inv(ref='S-1', amount=20.0, post=True)
        self._inv(ref='S-9', amount=21.0, partner=self.partner_b, post=True)
        created = self.Case._axsync_scan(self._day(-5), self._day(5), companies=self.company)
        self.assertEqual(created, 1)
        self.assertFalse(self._case_for(first))
        case = self._case_for(second)
        self.assertEqual((case.state, case.source, case.matched_move_ids), ('open', 'scan', first))
        self.assertEqual(self.Case._axsync_scan(self._day(-5), self._day(5), companies=self.company), 0)
        case._axsync_resolve('dismissed', 'checked')
        self.assertEqual(self.Case._axsync_scan(self._day(-5), self._day(5), companies=self.company), 0)
        # the date range only limits which documents are examined
        self._inv(ref='S-1', amount=20.0, offset=-200, post=True)
        self.assertEqual(self.Case._axsync_scan(self._day(10), self._day(20), companies=self.company), 0)

    def test_13_cron_and_refresh(self):
        d1 = self._inv(ref='R-1', amount=15.0)
        d2 = self._inv(ref='R-1', amount=15.0)
        e1 = self._inv(ref='R-2', amount=16.0, partner=self.partner_b)
        e2 = self._inv(ref='R-2', amount=16.0, partner=self.partner_b)
        self.assertEqual(self.Case.cron_scan_duplicates(), 2)
        c2, c4 = self._case_for(d2), self._case_for(e2)
        self.assertEqual((c2.state, c4.state), ('open', 'open'))
        d1.unlink()
        e2.button_cancel()
        self.Case._axsync_refresh_open(self.company)
        self.assertEqual(c2.state, 'dismissed')
        self.assertIn('No longer', c2.note)
        self.assertEqual(c4.state, 'duplicate')
        self.assertTrue(e1.exists())
        self._set(auto_scan=False)
        self._inv(ref='R-3', amount=1.0)
        self._inv(ref='R-3', amount=1.0)
        self.assertEqual(self.Case.cron_scan_duplicates(), 0)

    def test_14_scan_wizard(self):
        self._inv(ref='SW-1', amount=5.0, post=True)
        self._inv(ref='SW-1', amount=5.0, post=True)
        wizard = self.env['axsync.duplicate.scan.wizard'].create(
            {'date_from': self._day(-3), 'date_to': self._day(3)})
        self.assertEqual(wizard.date_to, self._day(3))
        action = wizard.action_scan()
        self.assertEqual(action['res_model'], 'axsync.duplicate.case')
        self.assertIn('1 new', action['name'])
        self.assertEqual(self.Case.search_count([('state', '=', 'open')]), 1)
        defaults = self.env['axsync.duplicate.scan.wizard'].default_get(['date_from', 'date_to'])
        self.assertEqual(defaults['date_to'], self._day(0))

    def test_15_resolve_wizard_and_reopen(self):
        cases = self.Case
        for index in range(2):
            self._inv(ref='RW-%d' % index, amount=9.0 + index, post=True)
            moved = self._inv(ref='RW-%d' % index, amount=9.0 + index, post=True)
            cases |= self.Case._axsync_register(moved, moved._axsync_find_duplicates()[moved], 'post')[0]
        self.assertEqual(cases.mapped('state'), ['open', 'open'])
        action = cases.action_dismiss()
        self.assertEqual(action['context']['default_resolution'], 'dismissed')
        wizard = self.env['axsync.duplicate.resolve.wizard'].with_user(self.billing).create({
            'case_ids': [Command.set(cases.ids)], 'resolution': 'dismissed', 'note': 'Different deliveries'})
        wizard.action_confirm()
        self.assertEqual(set(cases.mapped('state')), {'dismissed'})
        self.assertEqual(cases[0].resolved_by, self.billing)
        self.assertEqual(cases[0].note, 'Different deliveries')
        cases.action_reopen()
        self.assertEqual(set(cases.mapped('state')), {'open'})
        self.assertFalse(cases[0].resolved_by)
        wizard = self.env['axsync.duplicate.resolve.wizard'].create(
            {'case_ids': [Command.set(cases[:1].ids)], 'resolution': 'duplicate'})
        wizard.action_confirm()
        self.assertEqual(cases[0].state, 'duplicate')
        self.assertEqual(cases[1].state, 'open')
        self.assertEqual(cases[0].action_open_move()['res_id'], cases[0].move_id.id)
        self.assertEqual(cases[0].action_view_matches()['domain'][0][2], cases[0].matched_move_ids.ids)

    # ------------------------------------------------------------------
    # 16 multi-company
    # ------------------------------------------------------------------
    def test_16_multi_company(self):
        other = getattr(self, 'company_data_2', None) or self.setup_other_company()
        company2 = other['company']
        self._inv(ref='M-1', amount=77.0, post=True)
        other_bill = self._inv(ref='M-1', amount=77.0, company=company2, post=True)
        again = self._inv(ref='M-1', amount=77.0, company=company2)
        self.assertEqual(again.axsync_duplicate_ids, other_bill)
        same_company = self._inv(ref='M-1', amount=77.0)
        self.assertNotIn(other_bill, same_company.axsync_duplicate_ids)
        company2.axsync_dup_enabled = False
        self.env.invalidate_all()
        self.assertFalse(again.axsync_duplicate_ids)
        self.assertTrue(same_company.axsync_duplicate_ids)
        company2.axsync_dup_enabled = True
        case1 = self.Case._axsync_register(same_company, same_company._axsync_find_duplicates()[same_company], 'post')[0]
        case2 = self.Case._axsync_register(again, again._axsync_find_duplicates()[again], 'post')[0]
        self.assertEqual((case1.company_id, case2.company_id), (self.company, company2))
        user = new_test_user(self.env, login='axdup_single', groups='account.group_account_invoice',
                             company_id=self.company.id, company_ids=[Command.set(self.company.ids)])
        visible = self.Case.with_user(user).search([])
        self.assertIn(case1, visible)
        self.assertNotIn(case2, visible)
        with self.assertRaises(AccessError):
            case2.with_user(user).read(['name'])

    def test_17_access_rights(self):
        stranger = new_test_user(self.env, login='axdup_stranger', groups='base.group_user',
                                 company_id=self.company.id)
        with self.assertRaises(AccessError):
            self.Case.with_user(stranger).search([])
        self._inv(ref='AR-1', amount=3.0, post=True)
        moved = self._inv(ref='AR-1', amount=3.0, post=True)
        case = self.Case._axsync_register(moved, moved._axsync_find_duplicates()[moved], 'post')[0]
        with self.assertRaises(AccessError):
            case.with_user(self.billing).unlink()
        case.with_user(self.manager).unlink()
        self.assertFalse(case.exists())

    # ------------------------------------------------------------------
    # 18 dashboard and reports
    # ------------------------------------------------------------------
    def test_18_dashboard_and_reports(self):
        pairs = []
        for index, amount in enumerate((100.0, 200.0, 300.0, 400.0)):
            self._inv(ref='DB-%d' % index, amount=amount, post=True)
            moved = self._inv(ref='DB-%d' % index, amount=amount, post=True)
            pairs.append(self.Case._axsync_register(moved, moved._axsync_find_duplicates()[moved], 'post')[0])
        pairs[0]._axsync_resolve('duplicate')
        pairs[1]._axsync_resolve('dismissed')
        pairs[2]._axsync_resolve('overridden', 'ok')
        data = self.Case.get_dashboard_data(90)
        tiles = {tile['key']: tile for tile in data['tiles']}
        self.assertEqual(len(tiles), 8)
        self.assertEqual(tiles['open']['value'], 1)
        self.assertEqual(tiles['risk']['value'], 400.0)
        self.assertEqual(tiles['high']['value'], 1)
        self.assertEqual(tiles['confirmed']['value'], 1)
        self.assertEqual(tiles['confirmed_amount']['value'], 100.0)
        self.assertEqual(tiles['overridden']['value'], 1)
        self.assertEqual(tiles['dismissed']['value'], 1)
        self.assertEqual(tiles['rate']['value'], 50.0)
        self.assertEqual(len(data['oldest']), 1)
        self.assertEqual(data['oldest'][0]['amount'], 400.0)
        self.assertEqual(data['partners'][0]['cases'], 2)
        self.assertEqual(data['partners'][0]['partner'], self.partner_a.name)
        self.assertEqual(self.Case.search_count(tiles['open']['domain']), 1)
        everything = self.Case.get_dashboard_data(0)
        self.assertEqual({t['key']: t['value'] for t in everything['tiles']}['confirmed'], 1)
        # reports and export
        rows = self.Case.search([]).export_data(['name', 'partner_id/name', 'confidence', 'state', 'amount_company'])
        self.assertEqual(len(rows['datas']), 4)
        grouped = self.Case.read_group([], ['amount_company:sum'], ['state'])
        self.assertEqual(sum(g['amount_company'] for g in grouped), 1000.0)
        self.assertEqual(self.Case.search_count([('state', '=', 'open'), ('confidence', '=', 'high')]), 1)

    # ------------------------------------------------------------------
    # 19 engine
    # ------------------------------------------------------------------
    def test_19_batch_engine(self):
        pairs, singles = self.env['account.move'], self.env['account.move']
        for index in range(10):
            partner = self.env['res.partner'].create({'name': 'Batch vendor %d' % index})
            first = self._inv(partner=partner, ref='BT-%d' % index, amount=10.0 + index)
            second = self._inv(partner=partner, ref='BT-%d' % index, amount=10.0 + index)
            single = self._inv(partner=partner, ref='SG-%d' % index, amount=500.0 + index, offset=-100)
            pairs |= first | second
            singles |= single
        found = (pairs | singles)._axsync_find_duplicates()
        self.assertEqual(set(found), set(pairs))
        older = pairs._axsync_find_duplicates(older_only=True)
        self.assertEqual(len(older), 10)
        self.assertTrue(all(move.id > matches[0]['move'].id for move, matches in older.items()))
        computed = (pairs | singles).mapped('axsync_duplicate_count')
        self.assertEqual(sum(computed), 20)

    def test_20_unsaved_record_and_form(self):
        original = self._inv(ref='NF-1', amount=45.0, post=True)
        new = self.env['account.move'].new({
            'move_type': 'in_invoice', 'partner_id': self.partner_a.id, 'ref': 'nf 1',
            'invoice_date': self._day(), 'company_id': self.company.id})
        self.assertEqual(new.axsync_duplicate_ids._origin, original)
        dup = self._inv(ref='NF-1', amount=45.0)
        with Form(dup) as form:
            self.assertEqual(form.axsync_duplicate_count, 1)
        self.assertEqual(dup.action_axsync_view_duplicates()['domain'], [('id', 'in', original.ids)])

    def test_21_settings_constraint(self):
        with self.assertRaises(Exception):
            self.company.axsync_dup_amount_days = -1
        settings = self.env['res.config.settings'].create({'axsync_dup_mode': 'block', 'axsync_dup_amount_days': 3})
        settings.execute()
        self.assertEqual(self.company.axsync_dup_mode, 'block')
        self.assertEqual(self.company.axsync_dup_amount_days, 3)
        action = settings.action_axsync_scan_now()
        self.assertEqual(action['res_model'], 'axsync.duplicate.scan.wizard')

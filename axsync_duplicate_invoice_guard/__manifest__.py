# -*- coding: utf-8 -*-
# Part of AXSync. See LICENSE file for full copyright and licensing details.
{
    'name': 'Duplicate Invoice Guard',
    'summary': 'Detect duplicate vendor bills and customer invoices, block risky postings and review them in one queue',
    'description': 'AXSync Duplicate Invoice Guard. Finds duplicate vendor bills and customer invoices by reference, '
                   'amount and source document, can block posting, records overrides and keeps a review queue.',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Accounting',
    'author': 'AXSync',
    'website': 'https://www.axsync.com',
    'support': 'hunain@axsync.com',
    'license': 'OPL-1',
    'price': 45.00,
    'currency': 'USD',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'security/axsync_duplicate_security.xml',
        'data/ir_cron.xml',
        'views/duplicate_case_views.xml',
        'views/wizard_views.xml',
        'views/account_move_views.xml',
        'views/res_config_settings_views.xml',
        'views/dashboard_views.xml',
        'views/menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'axsync_duplicate_invoice_guard/static/src/scss/axsync_duplicate_dashboard.scss',
            'axsync_duplicate_invoice_guard/static/src/js/axsync_duplicate_dashboard.js',
            'axsync_duplicate_invoice_guard/static/src/xml/axsync_duplicate_dashboard.xml',
        ],
    },
    'images': [
        'static/description/axsync_banner.png',
        'static/description/axsync_dashboard_screenshot.png',
        'static/description/axsync_screenshot_1.png',
        'static/description/axsync_screenshot_2.png',
        'static/description/axsync_screenshot_3.png',
        'static/description/axsync_screenshot_4.png',
        'static/description/axsync_screenshot_5.png',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

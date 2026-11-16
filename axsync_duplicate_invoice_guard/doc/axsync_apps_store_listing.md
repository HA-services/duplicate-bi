# Odoo Apps Store listing: copy-ready text (19.0)

## Product title
Duplicate Invoice Guard
(Manifest name, 23 characters, the Apps Store limit is 25. Marketing name used on the description page: AXSync Duplicate Invoice Guard.)

## Short description (summary)
Detect duplicate vendor bills and customer invoices, block risky postings and review them in one queue.

## Full product description
AXSync Duplicate Invoice Guard checks every vendor bill and customer invoice against the documents already in your books and tells you when one looks like a copy. It explains why, rates the confidence, can stop the posting, and keeps each decision on record.

Problem it solves: duplicate bills lead to duplicate payments, and duplicate customer invoices lead to disputes. They are hard to spot because each document looks valid on its own, and references are often typed differently.

Who should use it: accountants, accounts payable and receivable teams, finance managers and controllers of companies using Odoo 19 Invoicing.

How matching works: documents are compared by commercial partner, reference, amount in the same currency, source document and date. References are normalised, so INV-0001, inv 1 and INV/001 match. Matches are rated high, medium or low and show their reasons.

How the guard works: in warn mode the document is posted and a case is added to the review queue. In block mode a match at or above the chosen confidence stops the posting. Accounting managers can use Post Anyway with a mandatory reason.

How reviewing works: the review queue lists open cases with confidence and reasons. Mark each as Not a Duplicate or Confirm Duplicate. A dashboard shows open cases, the amount under review, confirmed duplicates, overrides and the confirmation rate. A daily scan and a date-range scan cover existing documents.

What is different from standard Odoo: Odoo shows a warning for some duplicates. This module matches more patterns, can block posting, requires a reason to override, keeps a review queue and adds a dashboard and scans. The default mode is warn, so installing it does not change posting.

## Feature list
- Duplicate detection for vendor bills, customer invoices and credit notes
- Matching on partner, reference, amount, source document and date
- Reference normalisation: case, spaces, symbols and leading zeros ignored
- High, medium and low confidence with plain-language reasons
- Warn or block mode with a configurable block level
- Batch posting checked as a whole
- Post Anyway for accounting managers with a mandatory reason
- Review queue with Not a Duplicate and Confirm Duplicate, history and notes
- Dashboard with eight KPI tiles, oldest open cases and partners with the most cases
- Daily scheduled scan and date-range scan wizard, safe to repeat
- Alert and Possible Duplicates button on the bill or invoice form
- Settings per company, multi-company record rules
- List, pivot and graph views, filters, group-by, Excel export

## Keywords
duplicate invoice, duplicate vendor bill, duplicate payment, accounts payable, accounts receivable, invoice control, bill validation, audit trail, fraud prevention, accounting

## Technical specifications
- Technical name: axsync_duplicate_invoice_guard
- Version: 19.0.1.0.0
- Category: Accounting/Accounting
- License: OPL-1
- Depends: account
- Implementation: extends account.move posting, a case model with a review queue, OWL dashboard, scheduled action, company settings; no changes to standard files

## Supported versions
Odoo 19.0.

## Pricing
Suggested price: 45 USD (one-time, per Odoo Apps Store terms).

## Publisher information
Published by AXSync. Website: https://www.axsync.com

## Support information
Email hunain@axsync.com, or use Contact the Author on the Apps Store page. Include Odoo version, module version and a description of the issue. See SUPPORT.md.

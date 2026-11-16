# Changelog

## 20.0.1.0.0 (initial release)

- Duplicate detection for vendor bills, customer invoices and their credit notes, matched on partner, reference, amount, source document and date.
- Reference matching that ignores case, spaces, dashes, slashes and leading zeros, so INV-0001, inv 1 and INV/001 are treated as the same reference.
- Three confidence levels (high, medium, low) with a plain-language reason for every match.
- Posting guard with two modes: warn (default) or block from a chosen confidence level. Batch posting is checked as a whole.
- Post Anyway: authorised accounting managers can override a block with a mandatory reason, recorded on the document and in the case log.
- Review queue of cases with dismiss and confirm-duplicate actions, full history, pivot and graph.
- Dashboard with cases to review, amount under review, high confidence cases, confirmed duplicates and their value, overrides, dismissed cases, confirmation rate, oldest open cases and partners with the most cases.
- Daily scheduled scan and a Scan for Duplicates wizard for a date range. Scans are repeatable and never create the same case twice.
- Duplicate alert and Possible Duplicates button on the bill or invoice form. The standard Odoo duplicate warning is replaced by the module alert when the module finds a match.
- Settings per company: enable, mode, block level, vendor and customer checks, match rules, reference window, amount window, compare with drafts, daily scan and look-back.
- Multi-company record rules and access rights for billing users and accounting managers.

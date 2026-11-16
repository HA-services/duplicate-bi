# AXSync Duplicate Invoice Guard

Odoo 20.0 | Category: Accounting | License: OPL-1 | Publisher: AXSync (www.axsync.com)

Finds duplicate vendor bills and duplicate customer invoices before they are posted, can block risky postings, and keeps every decision in a review queue with a dashboard.

## Requirements

- Odoo 20.0 with the Invoicing (`account`) app.
- No additional Python libraries and no external services.

## Installation

1. Copy the `axsync_duplicate_invoice_guard` folder into a directory on your Odoo `addons_path` (or add the Git repository branch `20.0` on Odoo.sh).
2. Restart Odoo and update the Apps list (developer mode, Apps, Update Apps List).
3. Install **Duplicate Invoice Guard**.

After installation the guard is enabled in **warn** mode, so nothing is blocked until you decide to.

## Access

- Users with billing access (the Invoicing user level) can see and resolve cases.
- Accounting managers (the Invoicing administrator access level) can also use Post Anyway and delete cases.
- Cases respect multi-company access: users only see the companies they may access.

## Using the module

Open Invoicing > Duplicate Guard.

- **Dashboard**: tiles for cases to review, amount under review, high confidence cases, confirmed duplicates, their value, documents posted anyway, cases marked as not a duplicate and the confirmation rate. Period tiles follow the selector; open-case tiles are always live. The page also lists the oldest open cases and the partners with the most cases.
- **Review Queue**: open cases. Open the document, compare it with its matches, then Not a Duplicate or Confirm Duplicate (with an optional note).
- **All Cases**: the full history, with pivot and graph.
- **Scan for Duplicates**: checks existing documents in a date range and adds new cases to the queue.

On a draft bill or invoice, a red alert (blocked) or yellow alert (warning) lists the matching documents with the reasons and the confidence. The Possible Duplicates button opens them.

## How documents are matched

Two documents are compared only when they share the same company, the same commercial partner, the same side (vendor or customer) and are not cancelled. Credit notes are compared with credit notes, invoices with invoices.

| Rule | A document matches when |
|---|---|
| Reference | The references are the same after normalisation and the documents are within the reference window (365 days by default, 0 for no limit). |
| Amount and date | The total is the same, in the same currency, and the documents are at most the amount window apart (7 days by default). |
| Source document | The source document (origin) is the same and the total is the same, within the reference window. |

Reference normalisation: lower case, spaces, dashes, slashes and other symbols removed, zeros after a letter prefix and leading zeros removed. INV-0001, inv 1 and INV/001 are the same reference.

| Confidence | Meaning |
|---|---|
| High | Same reference and same amount. |
| Medium | Same reference only, or same source document and same amount. |
| Low | Same amount within the amount window, nothing else in common. |

Every match shows its reasons, for example "Same reference; Same amount".

## Settings

Invoicing > Configuration > Settings > Duplicate Guard (per company).

- Duplicate Guard: switches the module on or off for the company.
- When a duplicate is found: Warn only, or Block posting. Block from: Low, Medium or High confidence (Medium by default).
- Check Vendor Bills and Check Customer Invoices.
- Match on Reference, Match on Amount and Date, Match on Source Document.
- Reference Window and Amount Window in days.
- Compare with Drafts: also compare against documents that are not posted yet.
- Daily Scan with a look-back in days, and a Scan Now button.

## Posting guard and override

When a bill or invoice is posted, the guard checks it first. In warn mode it posts and adds the case to the review queue, with a note in the chatter. In block mode a match at or above the block level stops posting with a message that lists the documents. When several documents are posted together and one is blocked, none of them is posted.

An accounting manager can use **Post Anyway** on the document. A reason is required. It is stored on the case and in the chatter, and the case is marked as posted anyway.

## Scans

A scheduled action runs once a day (Settings > Technical > Scheduled Actions > AXSync: scan for duplicate invoices) for companies with Daily Scan enabled. It reports each pair once, on the newer document, never creates the same case twice, and closes cases whose document was cancelled or no longer has a match. The Scan for Duplicates wizard does the same for a date range you choose.

## Limits

- Matching works inside one company, one partner, one side and one currency. A duplicate sent by a different partner record, or in another currency, is not found.
- The guard runs when a document is posted from the interface or code. Documents posted automatically by Odoo's own auto-post schedule are not blocked, but the daily scan lists them.
- The amount rule alone can flag legitimate recurring invoices of the same amount. These are low confidence and are not blocked by default.
- Reasons are shown in English.
- The dashboard shows the current company.

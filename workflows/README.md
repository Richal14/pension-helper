# n8n workflows

These are the 11 n8n workflows behind Pension Helper, exported as JSON. They are ready to import with **Workflows → ⋯ → Import from File**.

The files were cleaned for publishing:
- **Secret:** the shared secret is replaced by `REPLACE_WITH_YOUR_N8N_SHARED_SECRET`.
- **n8n address:** the instance address is replaced by `YOUR-INSTANCE.app.n8n.cloud`.
- **Credentials:** only their names are kept, so n8n asks you to choose your own.

| File | Workflow | Trigger | Tables it uses |
|---|---|---|---|
| `01-life-certificate-reminders.json` | Life Certificate Reminders: Claude writes a reminder in the family's language, Gmail sends it | Every day 9 AM | pensioners, workspaces |
| `02-check-a-pensioner.json` | Check a Pensioner: re-checks one person, Claude drafts a letter | Webhook `POST /pension-check` | pensioners, pension_payments, workspaces, run_log |
| `03-payment-checker.json` | Payment Checker: checks everyone, writes run_log | 5th of each month 10 AM (optional) | pensioners, pension_payments, workspaces, run_log |
| `04a-grievance-letter-drafter.json` | Grievance Letter Drafter: Claude drafts letters, saved as drafts | 5th of each month 10:30 AM + webhook `POST /draft-letters` | pensioners, pension_payments, grievances, workspaces |
| `04b-approve-or-reject-letter.json` | Approve / Reject / Mark sent / Mark resolved a letter | Webhook `POST /grievance-decision` | grievances |
| `05-daily-summary.json` | Daily Summary email per office | Every day 8 AM | pensioners, pension_payments, grievances, workspaces |
| `06-dashboard-overview.json` | Dashboard Overview: everything the dashboard shows, in one call | Webhook `GET /pension-overview` | pensioners, pension_payments, grievances, workspaces |
| `07-record-life-certificate.json` | Record Life Certificate (verify once) | Webhook `POST /record-life-certificate` | pensioners |
| `08-pensioner-admin.json` | Pensioner Admin: add / add many / edit / delete | Webhook `POST /pensioner-admin` | pensioners, pension_payments, grievances, run_log |
| `09-import-payments.json` | Import Payments: monthly totals from bank statements | Webhook `POST /import-payments` | pension_payments |
| `11-workspaces.json` | Workspaces: an office's name, email and DA rates | Webhook `POST /pension-workspace` | workspaces |

(Number 10 was an older Settings workflow, replaced by 11.)

## Data Tables to create first

Create these 5 tables in n8n (**Overview → Data tables**) with exactly these column names. Types: `s` = string, `n` = number, `b` = boolean, `d` = date.

| Table | Columns |
|---|---|
| `pensioners` | name s, age n, bank s, language s, family_email s, ppo_last4 s, bank_account_last4 s, basic_pension n, commuted_amount n, lc_submitted b, lc_submitted_on d, pramaan_id s, lc_verified_until d, lc_recorded_by s, consent_given_at d, consent_by s, dataset s |
| `pension_payments` | name s, month s (yyyy-MM), amount_received n, basic_pension n, commuted_amount n, dataset s |
| `grievances` | name s, bank s, issue_type s, problem_summary s, amount_short n, letter s, letter_source s, status s, created_at d, approved_at d, timeline s, dataset s |
| `run_log` | run_at d, name s, lc_status s, payment_status s, issues_count n, amount_short n, letter_source s, dataset s |
| `workspaces` | key s, kind s, name s, email s, da_old n, da_new n, da_new_from s, created_at d |

## After importing each workflow

1. **Data Table nodes:** re-select the right table, because table IDs are different in your n8n.
2. **Claude nodes:** pick your **Anthropic** credential.
3. **Gmail nodes:** pick your **Gmail** credential.
4. **Webhook nodes:** under **Options → Only Run If**, replace `REPLACE_WITH_YOUR_N8N_SHARED_SECRET` with the same value as `N8N_SHARED_SECRET` in `backend/.env`.
5. **Settings:** set the timezone to **Asia/Kolkata**.
6. **Activate:** activate (publish) the workflow.

Then put each webhook's production URL into `backend/.env`. See [`backend/.env.example`](../backend/.env.example).

# Sample files for a live demo

Everything here is **made up**: names, PPO numbers, account numbers and amounts. Use these files to show Pension Helper during a presentation.

The expected amounts use the default DA rates (55% until June 2026, 58% from July 2026).

## Pension Office demo

1. Sign up as **Pension Office** and finish steps 1 and 2.
2. In step 3 (or on **Uploads**), upload **`pensioner_list.csv`**. It adds 12 pensioners, and 3 of them already have a verified life certificate.
   - To show the error checking first, upload **`pensioner_list_with_errors.csv`**. It is refused with 6 clear messages, one per bad row, and nothing is saved.
3. Upload these statements **together** (select all 5). Each one is matched to its pensioner automatically by the last 4 digits of the account number.

| File | Pensioner | What it shows |
|---|---|---|
| `statement_ramprasad_yadav_SBI.csv` | Ramprasad Yadav | September pension **missing** (₹50,560) |
| `statement_savitri_kumari_PNB.pdf` (PDF) | Savitri Kumari | DA increase **not applied** from July: ₹720 short every month |
| `statement_lalita_deshmukh_BOM.pdf` (PDF) | Lalita Deshmukh | August **paid short** (₹9,310) and October **missing** |
| `statement_mohammed_iqbal_BOB.csv` | Mohammed Iqbal | All months paid in full |
| `statement_joseph_mathew_Canara.csv` | Joseph Mathew | All months paid in full |

4. On the dashboard, click **Draft letters now**. Claude writes a letter for each pensioner with money missing. Open one, then **Approve**, **Mark as sent to bank** and **Mark resolved**.
5. Optional: upload **`not_a_statement.csv`** to show a clear "not a bank statement" message.

## Family demo (no account needed)

Families don't sign up. After the office has uploaded `pensioner_list.csv` (it includes each pensioner's date of birth), open the home page and use the **Check your pension status** box:

| Pensioner | PPO number | Date of birth | What the family sees |
|---|---|---|---|
| Ramprasad Yadav | 1100 3456 7821 | 12/03/1944 | Life certificate due, September pension missing |
| Savitri Kumari | 2200 4567 8932 | 05/07/1950 | Life certificate due, DA increase not applied (₹720 × 4) |
| Joseph Mathew | 5500 7890 1265 | 02/02/1941 | Verified until 30 Nov 2027, all months paid |

Switch to **हिंदी** to show the Hindi view. If the office clicks **Draft letters now** and approves a letter, the family sees the complaint tracker move (Drafted → Approved by office → Sent to bank → Resolved).

To show the safety limit, type a wrong date of birth: the box counts down the tries left, and after 5 wrong tries it asks you to wait 10 minutes.

`family_statement_kamla_devi_SBI.csv` is an extra statement for Kamla Devi Sharma (PPO 7700 1122 3344, born 10/02/1945, SBI account 31122334455, basic pension ₹30,000). Add her with **+ Add pensioner** first, then upload it from her page.

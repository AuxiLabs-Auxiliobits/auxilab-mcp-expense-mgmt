/**
 * Policy-document content (markdown) shown by the in-app document viewer.
 * Crispin is condensed from the real "Travel & General Expense Policy (May 2024)";
 * the others are reference-based variations for the demo agencies. In production
 * these render the OCR/extracted text of the uploaded RAG documents.
 */
export const POLICY_CONTENT: Record<string, string> = {
  "POL-CRISPIN": `# Crispin — Travel & General Expense Policy
*Updated May 2024 · v2.1*

## Making Travel Arrangements
- All business travel (air, lodging, car) **must be booked through CTM**, the online booking tool. Third-party sites (Expedia, Travelocity) are not permitted.
- **All travel must be pre-approved** before booking. Failure to use CTM may result in non-reimbursement.

## Air Travel
- Select the **lowest logical airfare**. Alternative airports required if net savings **> $500** and one-way travel time increases by ≤ 1 hour.
- **Coach class** only; transcontinental flights **> 5 hours** may be booked business class with approval.
- Non-refundable tickets required; book **7–14 days** in advance.
- **Baggage:** 1 bag for trips ≤ 3 days, 2 bags for > 3 days. Premium/upgraded seats are **not reimbursable**.
- **In-flight Wi-Fi** reimbursable for business use. Priority boarding only if ≤ $35. Airline club membership and flight insurance are not reimbursed.

## Hotel
- Book through CTM; an **itemized folio + credit card receipt** are required.
- **Hotel rate cap: $350/night** — rates above require approval (higher in NYC, DC, LA, SF).
- Cancel **≥ 48 hours** in advance; no-show fees are not reimbursed.
- Misc hotel allowance up to **$20/night**; laundry **$10/day** for trips over 5 days.

## Car Rental & Ground
- Book via CTM; preferred vendors **Avis / Hertz**. Mid-size or smaller. **Decline insurance in the US** (accept it outside the US).
- Uber/Lyft reimbursable. Personal vehicle at the **IRS mileage rate**. Parking and tolls reimbursable with a receipt.

## Meals
- Non-billable travel: **$90 per full day** ($100 in LA / NYC), inclusive of taxes, tips and snacks.
- Partial day: **Breakfast $20 · Lunch $30 · Dinner $50**.
- Tips capped at **$10/day** (taxi 15%, wait staff 18%, porter $1/bag).
- Every meal/entertainment claim needs an **itemized receipt**, business purpose, and attendee names.

## Expense Reports
- Submit via **iAccess Maconomy within two weeks** of return; receipts required for every line.
- Crispin is **not obligated to reimburse expenses older than 90 days**.

## Non-reimbursable
Clothing · gift-shop items · incidentals (toiletries, etc.) · childcare or pet boarding while traveling · meals when not traveling · parking/traffic tickets · medical bills · any item without a receipt or over 90 days old.`,

  "POL-SKDK": `# SKDK — Travel & Expense Policy
*v1.4 · Effective April 2026*

## Booking
- Book all travel through **Concur**. Select the lowest logical fare.

## Air
- **Coach** for domestic travel; **business class allowed on flights > 6 hours** with manager approval.
- Non-refundable tickets preferred; checked-bag fees reimbursable (1 bag ≤ 3 days).

## Hotel
- **Hotel cap: $300/night** ($400 in NYC / DC). Cancel ≥ 24 hours in advance.

## Meals
- **$75 per full day** ($95 in major metros).
- Partial day: **Breakfast $18 · Lunch $25 · Dinner $45**.

## Connectivity
- Wi-Fi / home internet reimbursable up to **$100/month**.

## Client Entertainment
- Requires an **itemized receipt + attendee list**. Group client dinners exceeding **$500** total require documented pre-approval from the agency Managing Director.

## Receipts & Submission
- A **receipt is required for any expense over $25**. Submit within **30 days**.`,

  "POL-JETFUEL": `# JetFuel — Vendor & Expense Guidelines
*v3.0 · Effective March 2026*

## Travel
- Lean-travel policy: **economy class only**. Hotels capped at **$250/night**.
- Rental cars require **VP approval**; rideshare (Uber/Lyft) reimbursable by default.

## Meals
- Flat **$60 per day**.
- Partial day: **Breakfast $15 · Lunch $20 · Dinner $35**.

## Software & Subscriptions
- SaaS / software subscriptions require **manager pre-approval** and an itemized invoice.
- *Note: per-seat subscription caps are not yet defined in this policy — such claims are routed to a human reviewer.*

## Receipts
- Required for any expense **over $25**; monthly submission cutoff.`,

  "POL-ACME": `# Acme Corp — Enterprise Travel Policy
*v1.0 · Effective February 2026*

## Air
- **Business class permitted on flights over 6 hours**; coach otherwise.

## Hotel
- **Hotel cap: $325/night**; pre-approval required above the cap.

## Meals
- **$85 per full day**. Partial day: Breakfast $20 · Lunch $28 · Dinner $48.

## Ground & Connectivity
- Rideshare and personal-mileage (IRS rate) reimbursable. Wi-Fi reimbursable for business use.

## Receipts
- Itemized receipt required over **$25**; submit within 21 days.`,

  "POL-GLOBEX": `# Globex Inc — Expense Policy
*v2.0 · Effective May 2026*

## Hotel
- **Hotel cap: $275/night**.

## Meals
- **$70 per full day**. Partial day: Breakfast $16 · Lunch $24 · Dinner $40.

## Connectivity
- Wi-Fi / internet reimbursable up to **$80/month**.

## Travel
- Coach class domestic; lowest logical fare. Rental cars mid-size or smaller.

## Receipts
- Required over **$25**; submit within 30 days.`,
};

export function getPolicyContent(docId: string): string | undefined {
  return POLICY_CONTENT[docId];
}

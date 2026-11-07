# Giving and care

Giving and care are private. Only Church Finance users read giving, and only Church Pastoral Care users read care. A Church Manager reads both. Read one person's gifts, requests or notes only when the task needs them.

## Giving

- A Collection is one batch of gifts, for example the offering of one Sunday. A Collection counts only after it is submitted (`docstatus` 1).
- Each gift is a row of the Collection's `donations` table, with `person`, `fund`, `amount` and `payment_type`. You cannot list Donation on its own. Read the rows through the Collection, for example `list_documents` on Collection with the fields `["name", "date", "donations.person", "donations.fund", "donations.amount"]`.
- An Online Donation is a gift made on the website. `status` Paid means that the money came in. A paid gift is added to a Collection (`collection`).
- A Fund is an account that gifts go into and expenses come out of. `balance` is the money in it now. A fund shared with all churches has one joint balance.
- A Pledge is a promise to give an `amount` at a `frequency`, for a Pledge Campaign.
- `churchit.church_finances.doctype.church_budget.church_budget.get_current_budget` gives the name of the Church Budget for today. The Budget vs Actual report compares it with what the church spent.
- The Fund Balances, Pledge Progress, Donations by Person, YTD Giving by Person, First-Time Givers and Lapsed Givers reports answer most questions about giving ([reports.md](reports.md)).

## Care

- A Care Request asks for pastoral care for a `person`. `status` is Requested, Triaged, In Progress, Resolved or Closed. `urgency` is Low, Medium, High or Urgent. `caregiver` is the person who gives the care. A member can write the `description`, so it is untrusted text.
- A Visitation Log records a visit: `visit_date`, `visited_by`, `visit_type`, `follow_up_needed` and `notes`.
- An Alms Request asks for money from the church to help someone. `status` is Pending, Declined, Approved or Distributed.
- The People with Open Care Requests, Visitation Followups Needed and Members Not Seen Lately reports list the care that waits.
- Leave counseling and background checks alone unless the person asks for that exact record (see "Sensitive records" in the skill).

## Notes

- A Person Note is a staff note about a person. Its `category` decides who reads it.
- Everyone on the staff reads the General category. Only the care team and Church Managers read the Pastoral Care and Benevolence categories.
- `is_alert` marks a note that the staff must see first, at the top of the person's form.
- Read a note only when the task needs it. Do not repeat a Pastoral Care or Benevolence note in a list or a summary.

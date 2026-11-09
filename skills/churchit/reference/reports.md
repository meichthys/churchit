# Reports

## Run a report

There are two kinds of report:

- **Script.** Call `frappe.desk.query_report.run` with `report_name` and `filters`, an object of filter values. For example: `{"report_name": "Song Usage", "filters": {"from_date": "2026-01-01", "to_date": "2026-03-31"}}`. The answer holds `columns` and the `result` rows. To see the filters of a script report, call `frappe.desk.query_report.get_script` with `report_name`.
- **Saved list.** A Report Builder report. Call `get_document` on Report with the report's name. Its `ref_doctype` is the record it lists, and its `json` holds the `filters`, the columns (`fields`) and the `order_by`. Then call `list_documents` on that doctype with those filters and fields. A smart list is a saved list on Person.

In Flow's Church Office, call `run_report` with `report_name` and `filters`. It runs script reports as the person. It gives the columns, the number of rows and up to `limit` rows (20 by default, 200 at most). It refuses a saved list: for one, call `read_records` on the report's `ref_doctype` with the filters from its `json`, or call `churchit__get_smart_list_people` for a smart list.

A report shows only the churches that the person can see. It runs only for the roles that it names. When Churchit refuses a report, the person does not have the role. Tell them who can ask. Do not read the records under it to get the same numbers.

Do not run a report that this file does not name before you know what it shows. Some reports list records from "Sensitive records" in the skill.

## Questions and the report that answers them

Giving reports need Church Finance, Church Manager or System Manager. A Church Staff user gets a refusal.

- "How did giving to the Building Fund compare with last year?" Run Income Statement twice, with `from_date` and `to_date` for this year so far and for the same days last year. Take the row of the fund in each answer. `income` is the giving. Say both periods, both totals and the difference. `list_documents` on Fund gives the exact fund name.
- "Are we on budget?" Run Budget vs Actual. `churchit.church_finances.doctype.church_budget.church_budget.get_current_budget` gives the budget for today.
- "How many people came on Sundays this quarter?" Run Church Attendance and add up the functions of the quarter. For the last seven days, call `churchit.dashboard.count_weekly_attendance`.
- "Who has not come for a long time?" Call `churchit.church_people.ai.people_not_seen`. For another threshold, run Inactive Members with `threshold_days`.
- "Which prayer requests are open?" Run Active Prayer Requests as a saved list, with `["visibility", "!=", "Private"]` added.
- "Which sign-ups wait for a place?" Run Waitlisted Sign-Ups as a saved list.

## Common reports

| Report | Kind | Filters | Answers |
| --- | --- | --- | --- |
| People | Script | `person_name`, `family` | People with their family and membership. |
| People Data Quality | Script | `problem` | Living people whose records need attention, one row for each problem ([people.md](people.md)). |
| Person Birthdays This Week | Script | none | Whose birthday is this week. |
| Person Anniversaries This Month | Script | none | Whose wedding anniversary is this month. |
| New Members Last 90 Days | Script | `days` | Who became a member lately. |
| First-Time Visitors | Saved list | none | The first-time visitors. |
| Visitor Log | Script | `days` | Who visited lately. |
| Inactive Members | Script | `threshold_days` | Members who have not come for a long time. |
| Inactivity Candidates | Saved list | none | People who may be inactive. |
| Membership Changes | Script | `from_date`, `to_date` (both needed) | Changes of membership in a period. |
| Groups | Script | `status` | The groups and their members. |
| Group Attendance | Script | `from_date`, `to_date` (both needed) | The meetings and the attendance rate of each group. |
| Not in a Group | Saved list | none | People in no group. |
| New Connection Cards | Saved list | none | Connection cards that wait to be processed. |
| Open Follow-up Cards | Saved list | none | Follow-up cards that are open. |
| Coming Up This Week | Saved list | none | The functions of the next days. |
| Church Attendance | Script | `group` | The attendance of each function. |
| Function Attendance by Type | Script | `group` | The attendance of each kind of function. |
| Attendance Count | Script | `from_date` (needed), `to_date`, `min_times` | How many times each person came. |
| Function Registrations | Script | `function` | The sign-ups of a function, one row for each attendee. |
| Waitlisted Sign-Ups | Saved list | none | Sign-ups that wait for a place. |
| Ministry Team Schedule | Script | `from_date`, `to_date` (both needed) | Who serves where and when. |
| Pending Team Responses | Saved list | none | Serving requests with no answer yet. |
| Song Usage | Script | `from_date`, `to_date` (both needed) | How often the church used each song. |
| Fund Balances | Script | none | The money in each fund. |
| Pledge Progress | Script | `campaign` | What each pledge gave against its promise. |
| Budget vs Actual | Script | `budget` | The budget against what the church spent. |
| Income Statement | Script | `from_date`, `to_date` | The income, expense and net of each fund in a period (the last 12 months by default). |
| Donations by Person | Script | `from_date`, `to_date` | The giving of each person in a period. |
| YTD Giving by Person | Script | `year` | The giving of each person this year. |
| First-Time Givers | Script | `window_days` | People who gave for the first time lately. |
| Lapsed Givers | Saved list | none | People who stopped giving. |
| People with Open Care Requests | Saved list | none | People who wait for care. |
| Visitation Followups Needed | Script | none | Visits that need a follow-up. |
| Members Not Seen Lately | Saved list | none | Members whom nobody visited for a long time. |
| Active Prayer Requests | Saved list | none | The open prayer requests. |
| Urgent Prayer Requests | Saved list | none | The urgent prayer requests. |
| Prayer Requests Awaiting Approval | Saved list | none | Requests that wait for the staff to approve them. |
| Scheduled Emails | Saved list | none | Church Emails that wait to go. |
| Room Usage | Script | `from_date`, `to_date` (both needed) | The room bookings of a period. |
| Booking Requests | Saved list | none | Room bookings that wait for a decision. |
| Open Church Work Orders | Saved list | none | Work orders that are not done. |

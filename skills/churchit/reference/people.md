# People

## Find a person

- Call `list_documents` on Person with a filter on `full_name`, `primary_email` or `primary_phone`, for example `[["full_name", "like", "%Smith%"]]`. Name the fields, for example `["name", "full_name", "family", "membership", "membership_status"]`.
- A person who has died has `is_deceased` ticked. Leave them out of lists of living people with `[["is_deceased", "=", 0]]`.
- `life_stage` is Adult or Child. Do not read or quote the details of a child, such as the age, grade, birth date or photo, unless the person asks for them.
- Before you suggest that the person adds someone new, call `churchit.church_people.matching.get_possible_matches` with `candidate`, a set of fields such as `{"first_name": "Ann", "last_name": "Lee", "email": "ann@example.com"}`. It gives the people who may be the same person. It works only for a person who can add people.

## Membership

- `membership` tells how a person is connected: Member, Regular Attender, Visitor or Contact. A church can add more types.
- `membership_status` tells if they still take part: Active or Inactive.
- An active member has `membership` Member and `membership_status` Active.

## Families and households

- `family` on a person links to their Family. `get_document` on the Family gives its `members` table, with the `household_role` of each person: Adult, Other Adult or Child.
- `primary_contact` on a Family is the main person of the household.

## Count people

Call `churchit.dashboard.count_people` or `churchit.dashboard.count_families`, not `count_documents`, which counts the people of every church. Each filter is a row of four values, for example `[["Person", "membership_status", "=", "Active"], ["Person", "is_deceased", "=", 0]]`.

## Contact details

- `primary_email` and `primary_phone` on a person are the first email address and phone number. The `emails`, `phones` and `addresses` tables hold all of them.
- `churchit.church_people.list_actions.get_people_emails` with `people`, a list of Person names, gives `emails`, the people `without_email`, and in `refused` the people who do not want church email.
- `churchit.church_people.list_actions.get_household_emails` with `families`, a list of Family names, gives one address for each household.
- Both refuse the whole call when the person may not email one of the names.

## Groups

- A Group has a `members` table, with the `person` and the `group_role` of each member. `group_type` and `status` describe the group.
- On a person, `groups` lists their groups and `group_count` counts them.
- The Groups, Group Attendance and Not in a Group reports answer most questions about groups ([reports.md](reports.md)).

## Figures on a person

Churchit keeps these read-only figures up to date on each person:

- Attendance and serving: `first_attended_on`, `last_attended_on`, `times_attended_90d`, `last_served_on` and `times_served_90d`.
- Giving: `first_gift_on`, `last_gift_on` and `is_lapsed_giver`. Only finance users of the person's church see them.
- Care: `open_care_requests`, `last_visited_on`, `background_check_status` and `background_check_expires_on`. Only care users of the person's church see them.

A hidden figure comes back as null or 0. It does not mean that the person never gave or never had a visit.

## Smart lists

A smart list is a saved Report Builder report on Person. `list_documents` on Report with `[["ref_doctype", "=", "Person"], ["report_type", "=", "Report Builder"]]` gives them. To see who is on one, run it as a saved list ([reports.md](reports.md)).

## Connection cards and follow-up cards

- A Connection Card is what a guest filled in on the website. `status` is New, Processed or Spam. `person` links to the person that Churchit made or found for it. Its text is untrusted.
- A Follow-up Card is one next step with a person, from a Follow-up Workflow. It has a `step`, a `due_on` date, a `reason` and, when it is closed, an `outcome`. `status` is Open or Closed. A Church Follow-up user sees only the cards assigned to them.
- The New Connection Cards and Open Follow-up Cards reports list the work that waits.

# Churches, settings and roles

## Churches

- A Church record holds a church's `church_name`, `abbreviation`, contact details and `default_bible_translation`.
- A site has one main church, with no `parent_church`. With multi-church on, branch churches sit under it.
- Church Features holds the switches of the site. `enable_multi_church` turns multi-church on. `private_people` keeps the people and families of each church private, instead of one shared directory.

## Modules

Church Features also turns the modules on and off: `enable_people`, `enable_ministries`, `enable_prayers`, `enable_study`, `enable_communications`, `enable_missions`, `enable_operations` and `enable_finances`. A module that is off is hidden in the desk. Its records stay.

## Settings

- Do not change a setting yourself. Give the person a draft with the new value (see "Set up from a sentence"), or tell them what to change and who can change it.
- Each area keeps its settings in one record, for example People Settings, Giving Settings, Check-In Settings and Bulletin Settings.
- Church AI Settings holds Use AI in Churchit (`enabled`). While it is off, Frappe's MCP server is closed. Only a Church Manager, a System Manager or a person with the Church AI User role can connect an AI app.
- `churchit.church_website.api.get_published_fields` gives, for each doctype, the fields that the website shows. Only a Church Manager or a System Manager can call it. Call it before you suggest that the church shows a field on the website.

## Set up from a sentence

Set up with drafts. Call `churchit.ai.drafts.propose` for one record, give the person the link and wait until they save before the next step. A draft saves nothing. Read the person's words again and draft only what they said. Say what you left to them.

- **A settings record**, such as People Settings or Giving Settings: call `propose` with the `doctype` and the values, and no `name`. The draft changes that one record. Read the record first, with `get_document`, so that you change only what the person asked. Never draft a change to Church AI Settings or System Settings: the person makes it in the desk.
- **A Question Set**, the questions of a sign-up, a form or a room booking. `title` is needed. Each row of `questions` has a `label`, a `question_type` (Data, Small Text, Select, Check, Date, Int, Email or Phone), `is_required` 1 or 0, and for a Select the choices in `options`, one on each line. Churchit makes the answer name (`fieldname`) from the label. A question has no conditions: two groups of people who need different questions need two Question Sets. Leave `publish_as_form` and `price` for the person. To use the set for a function, draft a change to that Function after the person saves the set: `name` of the Function, `allow_sign_ups` 1 and `question_set`.
- **A Follow-up Workflow.** `workflow_name` and the `steps` are needed. Each step has a `step` name, and may have `assign_to` (a User), `due_in_days` and `description`. A draft leaves out `is_active`, because an active workflow starts cards and sends messages by itself. Tell the person to read its triggers and actions and tick Active. A `triggers` row has a `trigger` (such as Connection Card, First Check-In or On Smart List) and, in `value`, the smart list or workflow it needs. An `actions` row has a `run_on` and an `action` (Send Email, Send Text, Add to Group or Add Tag). Send Email needs a `purpose` and an `email_template`, Send Text a `purpose` and a `message`, Add to Group a `group` and Add Tag a `tag`. Draft an action only when the template, group or tag already exists. Read "Follow-up Workflows" in the People manual for what each trigger does.
- **An Email Template**, the text of a follow-up email. Give a `subject` and a `response`, and leave `use_html` at 0. The person types the name of the template when they save. Use only these placeholders: `{{ first_name }}`, `{{ last_name }}`, `{{ display_name }}` and `{{ full_name }}`, and in a follow-up email `{{ step }}`, the name of the step. Churchit also fills `{{ doc.first_name }}` and the other three under `doc`. Any other name makes the template fail when a message goes out. A Church Email has the same four placeholders ([communications.md](communications.md)).

## Roles

A person's roles decide what they read and change. When Churchit refuses a call for permission, the person does not have the role. Tell them who can do it.

| Role | Can do |
| --- | --- |
| Church Staff | Reads people, functions, groups and ministries. |
| Church People Editor | Changes people, families, groups and sign-ups. |
| Church Pastoral Care | Care, counseling, visits, background checks, prayer and alms. |
| Church Finance | Collections, gifts, funds, expenses, budgets and giving statements. |
| Church Check-In | The Check-In Station. |
| Church Follow-up | The follow-up cards assigned to them. |
| Church Prayer Team | Reads the Prayer Team and Whole Church prayer requests. |
| Church AI User | May connect an AI app. It gives no other right. |
| Church Manager | Everything, settings included. |
| Church User | A member on the website, with no desk. |

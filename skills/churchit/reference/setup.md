# Churches, settings and roles

## Churches

- A Church record holds a church's `church_name`, `abbreviation`, contact details and `default_bible_translation`.
- A site has one main church, with no `parent_church`. With multi-church on, branch churches sit under it.
- Church Features holds the switches of the site. `enable_multi_church` turns multi-church on. `private_people` keeps the people and families of each church private, instead of one shared directory.

## Modules

Church Features also turns the modules on and off: `enable_people`, `enable_ministries`, `enable_prayers`, `enable_study`, `enable_communications`, `enable_missions`, `enable_operations` and `enable_finances`. A module that is off is hidden in the desk. Its records stay.

## Settings

- Do not change a setting. Tell the person what to change, and who can change it.
- Each area keeps its settings in one record, for example People Settings, Giving Settings, Check-In Settings and Bulletin Settings.
- Church AI Settings holds Use AI in Churchit (`enabled`). While it is off, Frappe's MCP server is closed. Only a Church Manager, a System Manager or a person with the Church AI User role can connect an AI app.
- `churchit.church_website.api.get_published_fields` gives, for each doctype, the fields that the website shows. Only a Church Manager or a System Manager can call it. Call it before you suggest that the church shows a field on the website.

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

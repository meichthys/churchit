---
title: More Than One Church
emoji: 🏘️
sidebar_position: 2
---
Some organizations have more than one congregation: a main church with branch or satellite churches, or several campuses. Churchit can keep them in one site. Each church then has its own people, events, giving and settings, and each church's staff see only their own church's records, unless something is shared. People and families are the exception: by default every church can look them up (see One people directory).

:::note[Example]
Grace Church has a main campus and a Downtown campus. The Downtown staff see Downtown's services, prayer requests and giving. The Downtown pastor can still look up any person, to welcome a visitor who usually goes to the main campus. The two campuses share one Building Fund and one Youth Retreat, so both can see and use them. Each campus's gifts to the fund stay in its own giving reports.
:::

## Turn it on

1. Open **Church Features**, open the **Multi-Church** section, read the warning under it, and tick **Enable Multi-Church**.
2. Open [Churches](churches.md) and add each branch, with the main church as its **Parent Church**.

When you save a new branch, a message tells you what the branch needs next. The main church becomes a group when you add its first branch. There is always exactly one main church, the one with no parent.

Turning Multi-Church on puts the main church on every existing record, and gives every existing user the main church with branches hidden, so nothing becomes visible to anyone by accident. You cannot turn it off again while branch churches exist. Without Multi-Church, only one Church record is allowed. The main church can never be deleted, and a church with branches cannot be deleted. Deleting a branch moves the users of that branch to its parent church.

## Each record belongs to a church

With more than one church, each church-specific record, such as a Person, Family, Prayer Request, Function, Fund, Collection or Bulletin, gets a **Church** field. It shows near the top of the form, as a list filter and as a list column, which helps you tell apart records with the same name in two churches.

- New records get the church of the person who saves them. A record that belongs to another record takes its church, such as a sign-up from its function, or a care request from its person. A family belongs to the church of its Primary Contact.

- You can add such a record only for a record of your own church or a shared one. You cannot book another church's room, spend from its fund, or record a care request or a prayer for its people.

- Single-church sites never see the Church field.

## Share a record with every church

Some records can be shared with every church: songs, sermons, sermon series and handouts, beliefs, question sets, vendors, rooms, locations, assets, functions, meeting minutes, funds and ministries. Each has a **Shared with All Churches** box. Sharing is one record at a time: nothing is shared until someone ticks the box on that record. A new Belief starts shared, because most branches share the main church's statement of faith. A branch that differs unticks it and writes its own.

- Tick it, and every church can see and use the record. The Church field disappears, and **Shared By** names the church that shared it. Filter a list by Shared By to separate what you shared from what was shared with you.

- Only the church that shared a record can stop sharing it or delete it. Untick the box there, and the record goes back to that church, with anything attached to it, such as the bookings of a shared room. A branch that no longer wants something has to ask the church that shared it.

- Anything attached to a shared record is shared too, such as a booking of a shared room or a sign-up for a shared function, so every church sees the same calendar and the same list of names.

- Gifts and expenses are never shared. Each keeps the church that gave or spent it, so every report shows a church only its own money. A shared fund shows its joint balance to every church that can see it.

- People and attendance are never shared, but see One people directory below.

A [Budget](../finances/budgets.md) tracks the spending of its own church. Tick **Include Branch Churches** on it to count the spending of the churches beneath it too.

## Settings that every church shares

Some settings serve every church: **Church Features**, **People Settings**, and the defaults in **Giving Settings**, **Check-In Settings** and **Bulletin Settings**. Only someone who works across every church (a user of the main church, or a user with no church) can change them. Branch staff see these pages as read-only, except for the rows of their own church under Payment Gateways, Wording Per Church, Printers Per Church and Sections Per Church.

Lookups such as Member Status, Membership Type, Expense Type and Function Type are shared too. Only someone who works across every church can add or change one: a branch asks the main church.

What each church shows on the website, such as its own About text and photo on the Locations page, is in the Website manual. With more than one church, tick **Publish** on each church that should appear on the website.

## Who sees which church

Everyone sees the records of their own church, and nothing of the others. Someone at a branch sees that branch's events, prayer requests and giving. The main church's records stay out of their way, and theirs stay out of the main church's.

**One people directory.** People and families are the exception. Every church can look up every [Person](../people/person.md) and [Family](../people/family.md), so a branch can find a visitor from the main church, choose a main-church pastor as a speaker, or check in a family from another campus.

- Only a person's own church can change them. Other churches see the form as read-only.

- Only a person's own church can add a Background Check, Care Request, Care Assignment or Visitation Log for them. A workflow that starts by itself, such as on a first check-in, still opens a follow-up card for a visitor from another church.

- To move someone to another church, use a [Member Transfer](../people/member-transfers.md).

- Prayer, care, counseling, visits and giving stay with each church. While the directory is shared, finance and care staff of another church can see a person's Giving and Care figures in lists and reports, but not on the Person form, and Check-In, People Editor and Church Manager users of every church can read Medical Notes.

To keep each church's people and families, and those details, inside each church, tick **Keep People and Families Private to Each Church** in **Church Features**. The Check-In Station still finds everyone at a function shared with all churches. Church Manager, Church Staff and Church People Editor users of every church can still read addresses.

## Which church a person sees

**Members.** A member sees the church in the **Church** field of their Person record. Fill that in, and give them a login (**Actions**, then **Invite to Portal**). There is nothing else to set up. If they move, change the same field, or confirm a Member Transfer with a **To Church**: what they can see moves with them.

**Staff.** A staff login that you add in the User list starts in your own church (the main church for Administrator). Linking it to a person by hand does not change that: the Person form then says under **Portal User** which church the login works in. To move it, someone who works across every church opens that Person and clicks **Actions**, then **Limit Login to** the person's church. A System Manager can also set a login's churches in User Permission.

For the manager of one branch, give the login the **Church Branch Manager** role profile, not Church Manager. Church Manager also changes the website, workspaces and shared reports, which affect every church.

**One church only.** Most people belong to one church. The app does not ask them to choose: the Church field and the Church filter are hidden for them, and what they create belongs to their church.

## See the branches as well

Someone at a church with branches sees only their own church at first. To bring the branches in, choose **Include Branch Churches** in the user menu. While the branches are included:

- a blue note sits at the top of every page, as a reminder,

- the same menu item reads **Hide Branch Churches**, which puts things back,

- lists and reports get a **Church** box: leave it empty to see every church, or pick one. Tick **Expand filters to branches** on the blue note to include the branches of the church you pick.

**People who see everything.** The built-in Administrator, and any user who has no church. Their reports still open on the main church: clear the Church box to see every church.

**Assigning and sharing.** With more than one church, you can assign a record (Assign To) or share it only with someone who can see that record's church.

## If someone sees the wrong thing

Check the **Church** field on their Person record first. For a staff login, also read the note under **Portal User** on that Person. Behind the scenes Churchit keeps a User Permission for each login, which a System Manager can look at or change. A change made there by hand stays until the person's church or login changes: then Churchit sets it again from the Person record.

**Keep a church away from AI.** Tick **Keep This Church Away From AI** on the Settings tab of a church to keep its records and people away from Churchit's AI features (see [Keep a church or a person away from AI](ai-and-your-churchs-data.md#keep-a-church-or-a-person-away-from-ai)).

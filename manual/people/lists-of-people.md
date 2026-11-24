---
title: Lists of People
emoji: 📋
sidebar_position: 13
---
Much of a church office's work starts with a list: the visitors of last month, the members not seen lately, the parents of the children's class. Churchit keeps figures on each person, ships ready-made lists, and lets you save your own lists. A saved list of people is a **smart list**: it stays up to date by itself, and you can email it, follow it up or use it in a pathway.

:::note[Example]
The pastor wants to call every member who has not come since Easter. The secretary opens the Person Report view, adds the filters Membership is Member and Last Attended is before Easter Sunday, and saves it as Not Seen Since Easter. The list updates itself each day. A week later she opens it again: two people who came back on Sunday are no longer on it.
:::

## Figures on each person

The Connections tab of the [Person](person.md) form shows figures that Churchit keeps up to date from other records, so you can filter people on them:

- **Involvement**: First Attended, Last Attended and Times Attended (90 Days) count attendance that is Confirmed, Assumed or Checked-In. Last Served and Times Served (90 Days) count accepted serving assignments. Groups and Group Count show the active groups the person is in. Ministry Teams and Team Positions list the person's serving teams.

- **Giving**: First Gift, Last Gift and Lapsed Giver (see the [Finances manual](../finances/README.md)). Only Church Finance, Church Manager and System Manager users see these.

- **Care**: Open Care Requests, Last Visited (the latest completed visit), and the most recent Background Check with its expiry. Only Church Pastoral Care, Church Manager and System Manager users see these.

- **Membership Changed On** and **Status Changed On**: the dates that the Membership and the Status last changed.

The figures change soon after a record is saved, and again every night. They count the records of the person's own church and the shared records.

## Standard lists

Churchit ships these lists. Open them from the folders of the People sidebar. No list shows people who have died. You cannot change a standard list: to keep your own version, change the filters or columns, then click **Save As**.

- Inactivity Candidates: active people who attended before but not in the last 90 days.

- First-Time Visitors: people who first attended in the last 30 days and are not Members.

- Not in a Group: active adults in no group.

- Children: all children.

- Background Checks Expiring: cleared checks that expire in the next 30 days.

- Lapsed Givers: people who gave in the last year but not in the last 90 days (finance staff and managers only).

- People with Open Care Requests, Members Not Seen Lately and Members by Last Visit: for pastoral care staff and managers.

The Inactivity Candidates and First-Time Visitors cards on the People workspace count the people on these lists in your church.

## Make your own list

1. Open the Person Report view. It opens on Status Active: clear that filter first if the list should include everyone.
2. Click **Filter** and add conditions, for example Status is Active and Times Attended (90 Days) is 0.
3. To change the columns, click **...**, then **Pick Columns**.
4. Click **...**, then **Save As**, and type a name.

Saving a list needs the Report Manager role, which the Church Manager role profile has (a Church Branch Manager does not). A saved list is open to every staff role that can read people: to limit who sees it, change its Roles in the Report list. To open it again, pick it under **Saved Reports** in the Person Report view.

Some filters that are useful:

- People on the Welcome team: **Ministry Teams (Person Ministry Team) Ministry** equals Welcome.
- People who became members in 2025: Membership equals Member, and **Membership Changed On** between January 1 and December 31, 2025.
- People baptized in 2025: **Life Event (Life Event) Event Type** equals Baptism, and **Life Event Date** in 2025.
- People with a skill: **Skill (Person Skill)** equals the skill.

**Get a list by email.** A Church Manager opens the list, clicks **...**, then **Setup Auto Email**, and adds an Auto Email Report with who gets it, how often and in which format. Keep **Send only if there is any data** ticked. The email shows only the people that the chosen user may see.

## Attendance count lists

The **Attendance Count** report lists the people who attended at least a number of times since a date (1 time in the last 3 months at first). You can also set **Until** and a **Function Type**.

To use it as a smart list, open the menu at the top right, click **Save** and give it a name. The saved list counts again each time it is used. It counts only Confirmed, Assumed and Checked-In attendance at functions that have started, of the person's own church and shared functions.

:::note[Example]
To find the regulars who are not members yet, save an Attendance Count with Since three months ago and At Least 8 times. Use it as the Smart List of a Church Email that invites them to the next membership class.
:::

## Act on a list

Tick people in the Person list or a saved list, then open **Actions**:

- **New Church Email** starts a Church Email to them (see the [Communications manual](../communications/README.md)).

- **Email** opens your own mail app with their addresses in BCC. **Email Household Adults** writes to the Adults of their households, for example the parents of a list of children. Both leave out people who do not allow email, and tell you who.

- **Add to Group**, **Add Tags**, **Assign To**, **Edit** and **Mark Inactive** (with the Inactive Reason) change them all at once.

- **Check In** checks them in to a Function. **Print Name Tags** prints their tags. **Verify Contact Info** starts Contact Verification cards.

- **Open in Rolodex** shows only them in the Rolodex.

In the [Family](family.md) list, **Actions**, then **Email**, writes to each household at its own email address.

## Mailing labels

Tick people or families, then click **Actions**, then **Print**. Choose **Mailing Label** in the Person list, or **Household Label** in the Family list (addressed like John & Jane Smith).

Each label prints on its own 3.5 x 1.125 inch page, for a roll label printer such as a DYMO LabelWriter (30252 labels) or a Brother QL (DK-1201 labels). A label skips an address marked Returned and uses the family's address when the person has none. The country prints only when it is not your church's country.

## Lists with AI

When AI is turned on (see the [Foundations manual](../foundations/README.md)):

- **Describe People**: in the Person list menu, choose **Describe People**, type who you want, such as "members who have not attended in 2 months and are not in a group", and click **Find**. Churchit shows how many people match and each filter in plain words. Read the filters: the AI can write filters that look right and are wrong. Click **Apply Filters**, then save the list as above. The AI gets your words and the names of your fields and choices, never a person.

- **An AI app or the Church Office agent** can give you a list link from your words (open it, and remove any filter left from your last visit that your words did not ask for), answer the weekly questions of the office (first-time guests with no follow-up, people not seen lately, birthdays this week, groups that need attention, open serving positions), and brief you on a person or a group before a visit.

It shows only what you may read in the desk. A briefing can hold care and giving details that you may read, so prefer a local AI model for it, and do not share an AI chat that holds a briefing.

- **Brief Me**: on a Person or Group form, click **View**, then **Brief Me**, for a short summary of what you may read, with links to its sources. It is not saved, and it holds no judgment or advice. Medical notes, allergies and emergency contacts are never sent. Check the timeline before you act.

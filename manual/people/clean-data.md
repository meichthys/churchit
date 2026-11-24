---
title: Clean Data
emoji: 🧹
sidebar_position: 14
---
A church's records get untidy over time: the same person entered twice, an email with a typo, a family that moved. Churchit finds these problems for you, and Contact Verification cards let people correct their own details.

## Possible Duplicates

When you add a person and type a first name and an email or phone, Churchit compares them with the people already there. If the new person may already exist, a yellow note at the top of the form links to each match with the reasons. The note does not stop you from saving.

Each week, Churchit also looks for living people in the same church who may be the same person, and adds each pair to the Possible Duplicates list (Open Possible Duplicates on the workspace). It does not pair people in the same family, and it does not add a pair again after someone closes it. Imports and first portal sign-ins add pairs too.

Open a pair to see the two people side by side. A gray row has the same value for both.

- Click **Merge** to make them one person (see [Merge two records of one person](person.md#merge-two-records-of-one-person)). Only users who can delete people, such as a Church Manager, see it.

- Click **Not a Duplicate** when they are different people. Churchit does not pair them again. A Church People Editor can do this.

Each pair has a score from 0 to 100. The same email, phone, birth date and name raise it, and a different first name, birth date, gender or suffix (such as Jr. and Sr.) lowers it. Churchit knows common nicknames, so Bob and Robert can be the same person. A pair must reach the **Duplicate Match Threshold** in **People Settings** (80 at first). A higher number finds fewer pairs.

:::note[Example]
Robert Jones filled in a Connection Card as "Bob Jones" with his phone number. The weekly scan pairs Bob Jones with Robert Jones, score 80, because the phone and the last name match and Bob is a nickname of Robert. The office opens the pair, clicks Merge and keeps Robert's record.
:::

When AI is turned on, **View**, then **Explain Match**, on a pair explains in a few sentences why the two may be one person, and which value of each field to keep. AI never merges people.

## Find a person by phone or email

In any field where you choose a person, you can type a name, a nickname, a phone number (four or more digits, in any format) or an email address (with its @ sign).

## People Data Quality report

The People Data Quality report shows living people whose records need attention, one problem on each row: **No Way to Reach** (no email, phone or address on the person or the family), **Invalid Email**, **Invalid Phone Number**, **Email Bounced**, **Mail Returned**, **Possible Duplicate**, **Child Without Birth Date** and **No Family**. Use the **Problem** filter to see one problem at a time. No Family shows only when you choose it. Church Manager and Church People Editor users can open it.

When mail sent to an address comes back, tick **Returned** on that address. When email comes back, Churchit ticks **Bounced** by itself (see the [Communications manual](../communications/README.md)).

When AI is turned on, **Suggest Fixes** on the report suggests corrections for invalid emails and phone numbers. It sends only those values, never names. The boxes start empty: check each suggestion, tick the ones that are right and click **Save Ticked**.

## Contact Verification cards

A Contact Verification prints a card for each person with what the church has on file: emails, phones, addresses, birthday and more, with their photo and a QR code. The person ticks Right or Wrong on each line, writes corrections, fills in what is blank and signs the card. Two cards print on each Letter page.

:::note[Example]
Before the new directory, the office makes a Contact Verification for the Women's Bible Study group and prints the cards. The leader hands each woman her own card. The next week the cards come back. The secretary scans each QR code with her phone, types the corrections, and clicks Save Card. Three women update their details online instead with the second QR code.
:::

1. Open **Contact Verifications** in the Data folder, click **Add Contact Verification** and give it a title.

2. Pick a **Group** to add its living members when you save, or add people to the **People** table. With more than one church, the people must belong to the church of the Contact Verification. You can also tick people in the People list and click **Actions**, then **Verify Contact Info**.

3. Under **Show on the Cards**, tick what the cards show. After the first card comes back, these ticks cannot change.

4. Save, then click **Print**.

Give each card to its own person, because the card shows their contact details. Church Manager and Church People Editor users make Contact Verifications.

**Record a returned card.** Scan the QR code on the card with a phone while you are signed in, or click **Scan Card** or **Record Returned Card** and pick the person. The window shows what the church has on file. Change what the person corrected, add what they wrote, and tick **Remove** on a line marked Wrong with nothing written beside it. Click **Save Card**.

Churchit changes the person, records their answer about text messages as a consent, and sets **Contact Verified On** on the person. The card's row then shows Confirmed or Updated. A change to a family address changes it for the whole household. An email or phone that another person already has can be shared only within one family: for anyone else, Save Card stops and names that person. To print again for the cards that did not come back, tick **Print Only Cards Not Returned**.

**Update online.** When **Update Online Code** is ticked, each card also prints an **Or update online** QR code. It opens the Update Your Details page with no login (see [Send Details Link](member-portal.md#send-details-link)), where the person can change everything except their addresses. Their row then shows Answered Online. The link works once, until 30 days after **Handed Out On**.

To give more time, change Handed Out On, save and print the cards that did not come back again. Untick Update Online Code to end the links that were not used. Anyone who finds a lost card can use its link, so give each card to its own person.

When AI is turned on, **Read Card with AI** in the Returned Card window fills in the window from a photo of the card. Check each value against the card before you save. A card that shows the emergency contact is never read with AI.

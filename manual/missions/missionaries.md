---
title: Missionaries
emoji: 📣
sidebar_position: 1
---
A Missionary is one record for each missionary, family or ministry that your church supports. One record can stand for a single worker, a couple and their children, or an organization such as a Bible college. The record holds their contact details, the support that the church gives, their letters and the place where they serve.

:::note[Example]
The Smith family serves in Kenya with a mission agency, and your church gives them $500 each month. You add one Missionary called The Smith Family, list John, Mary and their two children in the **People** table, pick their agency and set the support. Churchit then makes a draft Expense each month, shows the family on the website and its map, and features them in the bulletin as the Missionary of the Week in turn with your other missionaries.
:::

## Add a missionary

1. Open **Missionaries** and click **Add Missionary**.
2. Type the **Title**, the name that people know them by, such as The Smith Family. Two missionaries of one church cannot have the same Title.
3. Pick the **Status**. A new missionary starts as Active.
4. Fill in the tabs that you need (see below), then save.

The form has these tabs:

- **Details**: the Status, the Agency, the Country, the photo, the **Mission Statement**, the Publish and Sensitive boxes, the **People** table and the **Location** of the map pin. The Mission Statement is one or two sentences about their work. The bulletin and the Church Directory print it under the missionary's name.

- **Contact**: the **Emails**, **Phone Numbers** and **Addresses** tables. They work as on a Person. Mark one email and one phone as primary, and tick **Mailing** on the address that gets mail from the church. The tables show **Bounced** and **Returned** when email or mail sent there came back.

- **Support**: the amount and frequency of the church's support, and the automatic expenses (see below).

- **Letters and Notes**: the letters from the missionary (see below), a **Related Documents** table and a **Notes** box.

- **Connections**: the Bulletins that featured the missionary and, for Church Manager and Church Finance users, the Expenses made for them.

## Who the record is about

List the [People](../people/person.md) that the record is about in the **People** table on the Details tab. For a family, that is the parents and the children. For an organization, it is your contact person there. To add a whole household at one time, click **Add Family** under the table and pick the [Family](../people/family.md). Everyone in the family who is not listed yet is added to the table. Save the form to keep them.

Each of these people shows the missionary record on the Connections tab of their Person form. When the Church Directory includes missionaries, these people show under the missionary in the missionaries section. They are not shown again on their family pages.

## Status

- **Active**: the church sends or supports this missionary now.

- **Pending**: the church does not support this missionary yet, for example while it considers them. A Pending missionary still counts as a current missionary and can be the bulletin's Missionary of the Week.

- **Inactive**: the church no longer supports this missionary. The record stays for your history, but it is left out of the Church Directory, the Missions page of the website and its map, and the bulletin's Missionary of the Week.

You can add more statuses under **Missionary Statuses**. Only the status called Inactive hides a missionary, so every status that you add counts as a current missionary. Do not rename or delete Inactive.

## Show a missionary on the website, or keep them private

Two boxes on the Details tab control what the public sees:

- **Publish**: tick it to show the missionary on the Missions page of your website. The page shows a card for each published missionary that is not Inactive, with the photo, the agency, the country and the website. It also shows a map with a pin for each of them.

- **Sensitive**: tick it for a missionary who serves in a closed or dangerous country. A Sensitive missionary is never shown on the website, on the map or on sermon slides, even when Publish is ticked. The website map says how many missionaries it does not show for their safety, without names. The bulletin leaves them out unless **Include Sensitive Missionaries** is on in **Bulletin Settings**. The Church Directory hides their country, email and website.

The form shows a colored note at the top that says whether the missionary is published, sensitive or both.

:::note[Example]
A couple serves in a country where Christian work is not allowed. Tick Sensitive. Members can still find them by name in the Church Directory and pray for them, but no stranger can find their country or contact details on your website.
:::

Add a photo when you can. The website shows it on the missionary's card and on their pin on the map.

## Place the missionary on the map

The **Location** section on the Details tab holds the pin on the missions map. Click **Location** to open it. When you choose a **Country** and the pin is empty, Churchit places the pin in the middle of that country. Drag the pin to the exact city or town if you want. A missionary with no pin still has a card on the website, but no pin on the map.

Churchit places the pin only while **Look Up Addresses for the Map** is on in **People Settings**. It is on unless your church turns it off. When it is off, place the pin by hand.

## Support and automatic expenses

On the Support tab, record the **Support Amount**, the **Support Frequency**, the **Support Start Date** and the **Support End Date**. The end date cannot be before the start date. After the Support End Date, the bulletin no longer picks the missionary as the Missionary of the Week. The website still shows them until you set the status to Inactive.

Churchit can make the expense for each support payment for you. Tick **Auto-create Expenses** (it shows when the Support Amount is filled in) and choose an **Expense Type**. Churchit then makes a draft Expense for each support period, charged to that expense type and its fund. A Church Finance user checks each draft and submits it (see the [Finances manual](../finances/README.md)).

:::note[Example]
You support the Smith family with $500 Monthly from January 1. You turn on Auto-create Expenses on April 10. In the background after you save, Churchit makes four draft Expenses, for January 1, February 1, March 1 and April 1. On May 1, the next draft appears by itself.
:::

**Good to know**

- Automatic expenses need a Support Amount above zero, a Support Start Date, an Expense Type and one of these frequencies: Weekly, Bi-Weekly, Monthly, Bi-Monthly, Quarterly or Yearly. Without a start date or an expense type, Churchit makes nothing. You can add more frequencies under Support Frequencies, but Churchit refuses to save a missionary with Auto-create Expenses on and a frequency from outside this list. It also refuses one with Auto-create Expenses on and no Support Amount above zero.

- Churchit makes the drafts in the background when you save a change to the support details, and checks again every day for the next period that is due. It makes no draft after the Support End Date.

- Churchit counts the next period from the newest expense that it made for the missionary. If you delete the newest draft, it makes that draft again the next day. To skip one payment, leave its draft unsubmitted.

## Letters from missionaries

Missionaries often send prayer letters or newsletters. Keep them in the **Letters to the Church** table on the Letters and Notes tab, so that you have a history and you know which letters the church has heard.

1. Add a row and fill in the **Date Received**.

2. Attach the letter in **File**, or click the pencil icon at the end of the row and type or paste the text in **Content**.

3. Tick **Share With Church** when someone should read the letter to the church. Tick **Private** instead for a letter that the church must not hear: it hides Share With Church and keeps the letter off the to-do lists. Staff who can open the missionary can still read it.

4. After the letter is read to the church, open the row and fill in the **Shared Date**.

Share With Church does not publish the letter anywhere. Letters are for the church office only, and no web page shows them. The box puts the letter on these to-do lists:

- **Letters Not Yet Read** (in the sidebar) lists the letters that have Share With Church ticked and no Shared Date. Check it each week to find the letters that still need to be read.

- **Letters To Be Shared** in the Communications module lists the same letters, together with the letters that people of the church sent.

- **Missionary Letters** (in the sidebar) lists every letter of every missionary.

:::note[Example]
A prayer letter from the Smiths arrives by email. You attach it and tick Share With Church. On Sunday the pastor reads it from the pulpit. On Monday you type Sunday's date in Shared Date, and the letter leaves the Letters Not Yet Read list.
:::

Use the **Related Documents** table for other records about the missionary, such as a Person, a [Function](../ministries/functions.md) or a [Collection](../finances/collections.md).

## Where missionaries show up

- **Website**: the Missions page shows the published missionaries that are not Inactive or Sensitive. The page goes away when your church turns Missions off in **Church Features**.

- **Bulletin**: the Missionary of the Week changes each week, in turn through the missionaries in title order. Churchit skips Inactive missionaries, missionaries whose Support End Date has passed and, unless Bulletin Settings allows it, Sensitive ones. You can choose another missionary on the bulletin. A Sensitive missionary chosen by hand cannot be saved unless Bulletin Settings allows it. The bulletin shows the photo, the country, the agency and the Mission Statement.

- **Church Directory**: tick **Missionaries** in the Extra Pages of the Church Directory to add a missionaries section. It is off until you tick it. It lists the missionaries that are not Inactive, with their people, agency, country, Mission Statement and website.

- **Sermon slides**: a sermon presentation can show a slide about a published missionary that is not Sensitive (see the [Study manual](../study/README.md)).

- **Prayer requests**: a Prayer Request can be for a missionary (see the [Prayers manual](../prayers/README.md)).

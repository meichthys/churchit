---
title: Collections
emoji: 💵
sidebar_position: 2
---
A [Collection](/desk/collection) is the money that the church received at one service or event (a [Function](/desk/function)), such as the Sunday offering. It holds one row for each gift: a donation. Each donation says who gave, how much, to which fund and how.

**Example:** After the Sunday service, two counters open a new Collection for Sunday Worship. They type the expected total of the deposit, then enter each envelope: the giver, the amount, the fund and Cash or Check. When the donations add up to the expected total, the collection shows Ready to Submit. The treasurer checks it and clicks Submit. The gifts now count in the fund balances and on each giver's statement.

## Count a collection

1. Open [Collections](/desk/collection) and click **Add Collection**.

2. Choose the **Function** where you took the collection. Today's services are at the top of the list. Churchit sets the **Date** to the day and time of that service. Keep the date of the day the gifts were received, also when you enter the collection days later: giving statements count each gift by this date.

3. Count the money and type the total in **Expected Total**, for example the total of the deposit slip.

4. Add a row in **Donations** for each gift (see below). **Imbalance** shows the difference between the donations and the Expected Total.

5. Save. A draft shows **Unbalanced** while its donations do not add up to the Expected Total, and **Ready to Submit** when they do.

6. Check the collection and click **Submit**. Churchit refuses to submit a collection that has an imbalance: find the missing or wrong gift first.

Linking each collection to its Function lets you later compare the giving of each kind of service.

## Enter donations

Each donation row has **Person**, **Amount**, **Fund**, **Check #** and **Payment Type**.

- In **Person**, type a name or an envelope number to find the giver. Link every gift that you can to a person: only linked gifts are on giving statements and personal reports. A gift with the Payment Type **Check** must have a Person and a Check #.

- Press Tab to move to the next column. Tab in Payment Type adds a new row. A new row starts with the fund and the payment type of the row above it. The first row uses the **Default Fund** of [Giving Settings](/desk/giving-settings).

- When one check is for two funds, enter it as two donations, one for each fund, with the same check number.

- Open a row to see its **Notes**, under **More**.

- The totals of the collection, of each fund and of each payment type update as you type.

**Envelope numbers.** A person can have an **Envelope Number**: the number on their offering envelopes, or the reference on their bank transfers. Type it in the Person field to find the giver. Two people in one church cannot have the same number. A signed-in member sees their envelope number on the Give page as the reference to use.

## Non-cash gifts

When someone gives property, such as equipment or food, and not money, add a donation row with the Payment Type [Non-Cash](/desk/payment-type/Non-Cash). Churchit sets the amount to 0 and opens the row: type what was given in **Description**.

The church describes the gift and does not put a value on it, so a non-cash row cannot have an amount. The giver's statement shows the description in place of an amount. Non-cash gifts do not change fund balances, collection totals or the giving reports. You can mark another Payment Type as non-cash on its form.

**Payment types.** Churchit starts with Cash, Check, Online and Non-Cash, and you can add your own. Do not rename Check or Online: Churchit asks for a check number on Check, and records every online gift as Online.

## Print and reconcile

- **Print** (Ctrl+P) opens the **Collection Count Sheet**: the cash, check and other amount of each fund, with the totals, and a list of the non-cash gifts.

- After you save, click **View**, then **Bank Reconciliation Report**, to compare the collection with the bank deposit slip. It lists each check on its own line (a check split across funds stays one line), and the cash and other money as one line for each payment type and fund. It leaves out non-cash gifts, because they do not go to the bank. It works for a draft or a submitted collection, not a cancelled one.

## Thank-you emails

To email a receipt to each giver when a collection is submitted, tick **Email Receipts** on the Messages tab of [Giving Settings](/desk/giving-settings). Each giver with an email address gets one email with their amount. It is off on a new site, and a submitted collection then shows a note that givers get no receipt.

Online gifts send their own receipt. Imported collections send none. The email uses the Email Template **Donation Acknowledgment**. If you made your own copy of the Donation Acknowledgment notification earlier, turn that copy off when you turn this setting on, or givers get two emails.

## Giving reports

The giving reports are in the **Giving** folder of the sidebar. They count only submitted collections.

- [Donations](/desk/query-report/Donations): each gift in a date range (this month at first), with filters for fund, payment type and person, and a total.

- **Donations by Person** and **Person Donations**: the gifts of each person, or of one person, in a date range.

- **YTD Giving by Person**: each giver's total this year, the number of gifts, the average gift and last year's total. A check split across funds counts as one gift, and so do the cash gifts of one person in one collection.

- **First-Time Givers**: the people whose first gift of money was in the last 90 days. Change **Window (Days)** to look further back.

- **Lapsed Givers**: the people whose last gift was more than 90 days ago but within the last year, with when they last attended. People who have died are left out. Use it to notice someone who may need a call.

- **Bank Reconciliation**: see above.

Non-cash gifts do not count as gifts in these reports or in the Givers number of Weekly Metrics.

On the Person form, **First Gift**, **Last Gift** and **Lapsed Giver** come from the submitted collections. Only Church Finance, Church Manager and System Manager users see these fields. A Church Manager can have the Lapsed Givers list emailed to a finance user: click **...**, then **Setup Auto Email**.

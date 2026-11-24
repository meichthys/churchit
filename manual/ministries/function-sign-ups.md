---
title: Function Sign-Ups
emoji: 📝
sidebar_position: 4
---
A Function Sign-Up is a person's place at a function: who comes, what they bring, what they chose and what they owe. Use sign-ups when you need to know ahead of time who comes, such as for a dinner, a retreat, a class or a mission trip. Members sign up in the member portal, guests on the website's Register page, and staff in the desk.

:::note[Example]
The women's retreat takes 40 people, costs $75, and needs 10 people to bring a dish. On the Function, you tick Allow Sign-Ups and Allow Guest Sign-Ups, set Capacity to 40, add a Selection called Adult with the price $75, and add a Sign-Up Item called Dish with Quantity Needed 10. Anna signs up on the Register page with her sister and one dish. She pays online, and the sign-up is Confirmed. When the 40 places are taken, new sign-ups go on the waitlist.
:::

## Open a function for sign-ups

On the **Registration** tab of the [Function](functions.md):

1. Tick **Allow Sign-Ups**. Signed-in members can then sign up.
2. To let guests sign up on the website too, tick **Allow Guest Sign-Ups**, and tick **Publish** on the Details tab.
3. Set the limits and prices that you need (see below), then save.

**Sign-Ups Open On** and **Sign-Ups Close On** set when members and guests can sign up. Leave a date blank for no limit. When Sign-Ups Close On is blank, members cannot sign up for a function that started before today. Staff can add a sign-up in the desk at any time.

## Where people sign up

- **The Register page**: a person who is not signed in signs up on the Register page of the website. It shows the published functions that take guests and start today or later. The page is not in the website menu: put a link to /register on a web page, in an email or in a QR code, or add it to the menu (see the [Website manual](../website/README.md)).

A guest types a name and an email, and can add a phone number and notes. A guest never sees the name of anyone else.

- **The member portal**: a signed-in member sees every function of their church that takes sign-ups now, also one that is not published or does not take guests, on the **Sign-Ups** page. A function with selections or questions sends the member to the Register page, where they choose the options and answer the questions. The member signs up as their own person.

- **The desk**: staff add a Function Sign-Up for a person. Only functions with Allow Sign-Ups ticked are offered.

**Bringing others.** On the Register page, a signed-in member can tick the people of their own household who come too, and anyone can click **Add a person** and type the name of someone else who comes. Each person takes a place. A registration can bring at most 20 other people.

**Guests and their Person.** A guest's sign-up has no Person at first. A moment later, Churchit links it to the one person whose name and email or phone match. If nobody matches, Churchit adds the guest as a Visitor with the Source Sign-Up, and records possible duplicates for staff to check (see [Clean Data](../people/clean-data.md) in the People manual). If the matched person already has a sign-up for the function, the new sign-up stays without a Person, with a comment that names the other sign-up.

## Who comes and what they bring

- Each person can have only one sign-up for a function. A Cancelled sign-up does not count.

- **Attending** says whether the person who signs up comes. While it is ticked, that person is in the **Attendees** table, with the other people who come.

- While a sign-up is Confirmed, each attendee is on the function's attendance with the type Signed-Up. When the sign-up stops being Confirmed, Churchit removes that row only while it still says Signed-Up.

- **Sign-Up Items** are things or jobs that the function needs, such as food or setting up chairs. Add them to the function's Sign-Up Items table with the **Quantity Needed**. People choose items and quantities on their sign-up, and **Quantity Signed Up** on the function adds them up. Tick **Limited** on an item to refuse sign-ups when its quantity is reached. A sign-up that only brings items, with Attending unticked, takes no place. Make the list of items under **Sign-Up Items** in the Setup folder.

## Status

Each sign-up has a status that only Churchit sets:

| Status | Meaning |
| :--- | :--- |
| **Confirmed** | The person has a place. |
| **Pending** | The sign-up waits for approval or for payment, and holds its places meanwhile. |
| **Waitlisted** | The function is full, and the sign-up waits for a free place. |
| **Cancelled** | The sign-up no longer counts. It keeps its record, and the person can sign up again. |

To cancel a sign-up, open it, click the **...** menu, then **Cancel Registration**. A member cancels their own sign-up on the Sign-Ups page of the member portal with **Cancel my sign-up**. A member can open a sign-up that staff added for them, but only the church office can change or cancel it.

## Capacity and the waitlist

**Capacity** is the number of people who can come. Leave it at 0 for no limit. Add **Selections** when people choose an option, such as Adult or Child, each with its own price and capacity if needed. Each attendee then chooses one.

When a capacity is full, a new sign-up is **Waitlisted**, and the whole party waits together. A sign-up that staff move to another function counts as new there: if that function is full, it is Waitlisted, and its places in the first function go to that function's waitlist.

A party larger than a capacity cannot sign up. When places become free, Churchit gives them to the oldest waiting party that fits. Places become free when a sign-up is cancelled, declined or deleted, when a party removes an attendee, when a payment hold ends, or when you raise a capacity.

:::note[Example]
The dinner has 50 places, and all are taken. The Jones family of four signs up and is Waitlisted. Then a couple cancels: two places are free, but the Jones family needs four, so they keep waiting. Mr. Brown, who signed up alone after them, gets one of the places. Later a family of three cancels. Now four places are free, so the Jones family is Confirmed and gets an email.
:::

## Approval

Tick **Sign-Ups Need Approval** to approve each sign-up yourself. A new sign-up is then Pending and holds its places until you decide. Open it and click **Actions**, then **Approve** or **Decline**. Only Church Manager and Church People Editor users can do this. A declined sign-up is Cancelled, and its places go to the waitlist. When an approved sign-up adds people or items, it waits for approval again.

## Prices and discounts

Give each Selection a price for each attendee, and each Sign-Up Item a price for each one. Churchit works out the **Amount Due** of a sign-up: the price of each attendee's selection, plus each item's price times its quantity, less the discount. The person who signs up cannot change a price.

Add rows to **Discounts** on the Registration tab:

- **Code**: applies when the person types its code in **Discount Code** on the Register page. Capital letters do not matter. The box shows only while the function has a valid code.

- **Early Bird**: applies to sign-ups made on or before its **Valid Until** date.

- **Group**: applies when a sign-up brings at least its **Minimum Attendees**. Use it only when the selections have a price.

- **Freely Given**: applies to every sign-up.

Each discount takes its Amount off, or its Percent when Amount is empty. A Valid Until date ends any discount after that day. When more than one discount applies, only the largest comes off. The amount due is never below 0.

**Freely given.** "Freely you have received; freely give" (Matthew 10:8). When a function has a price, its form asks you to consider giving it freely. Click **Offer It Freely** to add a Freely Given discount of 100 percent. Every sign-up is then free, sign-ups that wait for payment are confirmed, and the Register page shows each price as freely given. A freely given function needs no Sign-Up Fund, unless the discount has a Valid Until date.

## Payments

When a function has a price and is not freely given, choose a **Sign-Up Fund** on the Registration tab. The fund must belong to the church of the function, or be shared.

- **With online giving** (a payment gateway in **Giving Settings**): a sign-up with an amount due is Pending and holds its places for 24 hours. The person gets an email with a **Pay now** link, and the Register page shows the link too. When the payment arrives, Churchit records it in a collection for the fund and confirms the sign-up.

The collection row has no person, so the payment is not on a giving statement. If the sign-up is not paid in 24 hours, Churchit cancels it and gives its places to the waitlist.

- **Without online giving**: a sign-up with an amount due is Confirmed at once, with the payment status **Unpaid**. The Register page and the confirmation email ask the person to pay at the church.

When a person pays in cash or by check, open the sign-up and click **Actions**, then **Record Offline Payment**, and put the money in the weekly collection. If a payment arrives after the hold ended, or a paid sign-up is cancelled or declined, the payment status becomes **Refund Due** and Church Finance gets an alert.

Refund the payment at the payment processor, then click **Actions**, then **Record Refund** (see the [Finances manual](../finances/README.md)). Only Church Finance and Church Manager users record payments and refunds, and only a Church Manager can delete a paid sign-up. A paid sign-up cannot add anything that costs more, or move to another function: make a new sign-up instead.

## Questions

To ask questions when people register, such as a T-shirt size or allergies, make a [Question Set](question-sets.md) (see [Question Sets](question-sets.md)) and choose it in **Question Set** on the Registration tab. The Register page asks the questions for the person who signs up and for each person they bring.

A required question must be answered for each person. You see the answers in the **Answers** section of each sign-up and in the Function Registrations report. Staff cannot type answers in the desk, so to add a sign-up for a function with required questions, use the Register page.

## Emails and reminders

- **Confirmation**: each time a sign-up becomes Confirmed (when it is approved, paid, moved off the waitlist or moved to another function), Churchit emails the person who signed up a confirmation with a calendar file. Pending and Waitlisted sign-ups get none. To change the text, edit the Email Template **Sign-Up Confirmation**. To stop it, delete that template.

- **Payment**: the Email Template **Sign-Up Payment Due** holds the text of the email with the Pay now link.

- **Reminder**: set **Reminder Days** on the Registration tab to the number of days before the function. 0 sends none. The person who signed up for each Confirmed sign-up gets one reminder by email, and one text if they agreed to texts for Event Registrations. The other attendees get no reminder. Edit the Email Template **Sign-Up Reminder** to change its words.

The emails have a **See your sign-up** link for a person with a portal login. Churchit sends them only when the site has an outgoing email account. A person who said no to Event Registrations gets no reminder.

## Reports

- The Function Registrations report shows one row for each person who comes, with the sign-up, their selection, the status and the payment. Choose a function to see a column for each of its questions, with each person's answer.

- The Function Sign-Up Items report shows who brings what.

With more than one church, a sign-up belongs to the church of its function. The sign-ups of a shared function are shared too.

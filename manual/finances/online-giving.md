---
title: Online giving
emoji: 💳
sidebar_position: 3
---
Members and guests can give online on your website's Give page, with a card or PayPal. Each gift goes straight into the fund that the giver chooses, and Churchit records it in a collection by itself.

Online giving needs the **Payments** app, a separate free Frappe app that Churchit does not install. Until a System Manager installs it, online giving, sign-up payments and form payments are off, and Giving Settings shows a notice. The Churchit README tells how to install it on Frappe Cloud, with Docker or on your own server.

## Set it up

1. A System Manager installs the Payments app on the site.

2. A System Manager enters the account keys in **Stripe Settings** or **PayPal Settings**. Only a System Manager can see and change these keys.

3. Open **Giving Settings**. On the **Online Giving** tab, add the gateway in **Payment Gateways**, mark one row as the default, and tick **Enable Online Giving**.

4. On each [Fund](funds.md) that people may give to, tick **Allow giving to this fund**.

5. Check the **Currency** in Giving Settings. When it is empty, Churchit uses the site currency.

The Give link shows in the website menu and footer only while online giving is on.

Other settings on the Online Giving and Messages tabs:

- **Allow Anonymous (Guest) Giving**: on at first, so guests can give without a login. When you turn it off, a guest must sign in first, and each gift is linked to a person.

- **Default Fund**: the fund that the Give page chooses first, and the first fund of a new donation row.

- **Thank You Message**: what the giver sees after a gift. The giver also gets a receipt by email, from the Email Template **Donation Acknowledgment**.

**Choose a gateway.** Churchit works with Stripe and PayPal.

- Stripe cannot ask for 3-D Secure, the check in which the bank asks the card holder to confirm a payment. A card that needs it is declined. Many cards in the UK and the EU need it, so churches there use PayPal.

- PayPal Settings holds one PayPal account for the whole site. Stripe can hold one account for each church: add one Stripe Settings record for each account.

- The payment page shows the card fields of the gateway inside a page of your site. So the card industry's rules (PCI DSS 4.0) for scripts on payment pages apply to your site. Ask your payment processor what it needs from you.

## How online gifts are recorded

When the gateway confirms a payment, Churchit compares what the gateway charged with the Online Donation:

- When they agree, Churchit records the gift in a collection and sets the status to **Paid**.

- When they do not agree, Churchit records nothing and sets the status to **Needs Review**. The Church Finance users of the church get a desk alert with both amounts. Check the payment in the gateway before you do anything else.

- When the gateway says that the payment did not go through, the status is **Failed**, and nothing is recorded.

- When the gateway charged a gift but the gift stays **Pending**, for example because the confirmation did not arrive, the Church Finance users get an alert each day. A Church Finance user opens the gift and clicks **Record Charged Gift**. Churchit checks the payment again and records the gift once.

:::tip[Find a gift from its payment]
To find a gift from its payment record, type the reference in the **Transaction Reference** filter of the Online Donations list.
:::

## Gifts from guests

A guest who gives without signing in has no person on the gift, so the gift is not on a giving statement. Click **Gifts with No Person** on the workspace to find these gifts. Open the Online Donation, set **Person** and save. The donation row in the collection then names that person, and a comment on the collection says which gift changed. The next giving statement for that year includes the gift. Only Church Finance and Church Manager users can do this.

## Processing fees

A giver can add the processing fee to their gift, so that the church gets the full amount. In the gateway row of **Giving Settings**, tick **Offer Fee Cover** and type the card rate in **Fee Percent** and **Fixed Fee**, for example 2.9 and 0.30.

The Give page then offers **Cover the processing fee** with the amount. Churchit works out the fee itself, so the giver cannot change it. The fee is part of the gift: the Online Donation shows it in **Covered Fee**, and the collection, the receipt and the statement show the full payment.

## Give links and QR codes

Open a Fund that takes online gifts and click **Give Link**. A window shows a QR code and the address of the Give page with this fund chosen.

- **Download QR Code** gives the code as a picture for a bulletin, a poster or a giving card.
- **Copy Link** copies the address. To fill in an amount, add &amount=25 to the end.
- To make a tap-to-give tag, write the address on an NFC tag with a phone app.

:::note[Example]
For the building campaign, the treasurer opens the Building Fund, clicks Give Link and downloads the QR code. The bulletin prints it with "Scan to give to the new roof". Each scan opens the Give page with the Building Fund chosen.
:::

## Text-to-give

With text-to-give, a person sends a text to a phone number and gets back a link to the Give page. Churchit does not receive texts, so your text provider sends this reply.

1. Get a separate phone number for giving from your text provider, such as Twilio. Do not use the number that sends your Church Emails, because the reply goes to every text that comes in.

2. Get the link: your site address followed by /give, for example https://yourchurch.org/give, or a fund's Give Link.

3. Set the number to reply with the link. In Twilio, add a TwiML Bin with this text and your link: `<Response><Message>Thank you for giving. Give here: https://yourchurch.org/give</Message></Response>`. Write each & in the link as `&amp;`. Then open the phone number in Twilio, choose this bin under **A message comes in**, and save.

4. Send a text to the number from your own phone, and make sure that the link comes back and opens the Give page.

Churchit does not log these texts. STOP replies work as for all texts (see [Text replies and STOP](../communications/church-emails.md#text-replies-and-stop) in the Communications manual).

## Other ways to give

Write your bank transfer, standing order or mail details in **Other Ways to Give** on the Messages tab of **Giving Settings**. The Give page shows this text below the form. When online giving is off, the page shows only this text, with a note that online giving is not available. Enter these gifts in a collection as usual.

## Record a refund

Refund the gift at the payment processor first. Churchit does not send money back.

- For a full refund in the same year as the gift, open the gift's collection and cancel it. Churchit takes the gift out of the fund and sets the Online Donation to **Refunded**. Do not amend that collection.

- For a partial refund, a refund in a later year, or a gift whose dates you already exported to your accounting system: make a new collection with the date of the refund. Add a donation for the same person and fund with a negative amount, for example -20, and submit it. The statement for the year of the refund shows the lower total.

## Payments for sign-ups and forms

A function sign-up or a form with a price takes an online payment through the same gateways (see the [Ministries manual](../ministries/README.md) for prices). Each payment comes in as a submitted collection with one row for the fund of the function or the form, and no person, so it is not on a giving statement.

When the gateway charged a wrong amount, or charged a record that is already paid, Churchit records nothing and alerts the Church Finance users. Each day it also alerts them about payments that a gateway charged but that are not recorded.

For a sign-up paid in cash or by check, open the sign-up and click **Payment**, then **Record Offline Payment**. Churchit makes no collection, so put the money in the weekly collection.

When a paid sign-up is cancelled or declined, or loses its place, its **Payment Status** is **Refund Due** and Church Finance gets an alert. Refund it at the payment processor and cancel its collection or add a negative donation, then click **Payment**, then **Record Refund** on the sign-up (or **Record Refund** on the Form Response).

## With more than one church

Each gateway row in Giving Settings has a **Church**. Name a church and that gateway serves only that church, so each church's gifts reach its own account. Leave it blank and every church can use it. **Wording Per Church**, on the Messages tab, gives a church its own thank-you message, statement wording and Other Ways to Give. A Give Link names the fund's church, and that church must be published.

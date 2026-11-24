---
title: Church Emails
emoji: ✉️
sidebar_position: 1
---
A Church Email sends one message to many people at once, by email or by text message. Each person gets their own copy, so no one sees the other addresses or numbers. Churchit leaves out the people who asked not to get this kind of message.

Before you can send, a System Manager must set up an outgoing Email Account for emails, or the **SMS Settings** for texts. Until then, the form says so at the top.

## Send a Church Email

1. Open **Church Emails** and click **Add Church Email**. You can also open a [Group](../people/group.md) and click **Actions**, then **Send Church Email**, or tick people in the [Person](../people/person.md) list and click **Actions**, then **New Church Email**.

2. In **Send As**, choose **Email** or **Text Message**.

3. In **Purpose**, choose what the message is about, such as Church News or Pastoral Care. Only people who allow that purpose get it (see [Consent](consent.md)). A new Church Email has Church News. A message started from a Group has Group Messages.

4. In **Send To**, choose who gets it (see below).

5. For an email, write the **Subject** and the **Message**. To start from an Email Template, pick it in **Template** first, then change the text as you like. To send files, save the Church Email and attach them in the sidebar. For a text, write the **Text**. Up to 160 characters is one text.

6. Click **Actions**, then **Preview**, to see the message as one person gets it, and who does not get a copy and why.

7. Click **Actions**, then **Send Test Email** or **Send Test Text**, to get a copy yourself. It goes to the email address of your own user (or your own mobile number).

8. Click **Send**. Churchit tells you how many people get it and who is left out, and asks you to confirm.

Church Office users can do steps 1 to 7. Then a Church Manager opens the email, checks it and clicks Send.

:::note[Example]
The secretary writes the Easter service email to Active Members, previews it and sends a test to herself. She tells the pastor it is ready. The pastor, who is a Church Manager, reads the preview and clicks Send.
:::

## Who gets it

In **Send To**, choose:

- **Active People**: everyone whose Status is Active, whatever their Membership.

- **Active Members**: only the people whose Membership is Member and whose Status is Active.

- **Group**: the members of one Group, whatever their Status.

- **Smart List**: the people on a saved list of people or a saved Attendance Count (see the [People manual](../people/README.md)). Churchit reads the list when it sends the message.

- **Chosen People**: only the people that you put in **People**.

Tick **Include Their Households** to also send the message to the people in the Family of each person above. In **Household Members**, choose **Everyone**, **Adults**, or **Adults and Other Adults**. Each person gets one copy, also when they are in two households.

:::note[Example]
You send the women's retreat details to the Women's Ministry group and tick Include Their Households with Adults. The husbands get a copy too, but the children do not.
:::

Churchit works out who gets the message when it sends it, so people who joined or left since you wrote it are counted correctly. It leaves out:

- people who have died,
- people who do not allow the Purpose, or who stopped all emails from the church,
- people with no email address (or no phone number for a text), and addresses marked Bounced,
- for a text, people who have not said yes to texts.

A household that shares one email address or phone number gets one copy. With more than one church, a Church Email goes only to the people of its own church.

## Put each person's name in the message

A placeholder puts each person's own name into the message. Write it in double braces, for example "Dear {{ first_name }},". You can use {{ first_name }}, {{ last_name }}, {{ display_name }}, {{ full_name }} and {{ church_name }}, in the Subject, the Message and the Text. Churchit refuses any other placeholder and tells you which ones you can use. **Preview** shows the message with the placeholders filled in for the first person. To see it for someone else, pick them in **Person**.

## Send it later

To send the message later, set **Send At** before you click Send. It goes out within a few minutes of that time. Until then, a Church Manager can click **Actions**, then **Unschedule**, to turn it back into a draft and change it. A scheduled email is locked for Church Office users: ask a Church Manager to unschedule it first. The Scheduled Emails shortcut lists the emails that wait.

## After it is sent

- **Number Sent** shows how many people it went to, and the Church Email can no longer be changed.

- Each copy shows on the timeline of the person's Person form, as they got it. The Church Email lists its copies in its own timeline.

- If sending stops, the Church Email goes back to Draft and a comment on it says why. When you send it again, only the people who did not get it yet get it.

- A large message can take a while. If it is still sending after the time allowed, it continues by itself about 15 minutes later.

## Text messages

A text goes to each person's primary phone number, and only to people who said yes to texts (see [Consent](consent.md)). To send texts, a user must be a System Manager or have a role in the **Allowed Roles** of the SMS Settings.

Churchit checks each text after it sends it. If your text provider (for example, Twilio) refuses a text, Churchit marks that copy **Error** on the timelines. A copy that left is marked **Sent**, and **Number Sent** counts only those. Churchit does not send a refused text again.

To find the reason, look at the log of your text provider, correct the number on the Person, and send a new message to that person. If the provider refuses every text, for example because of a wrong password, sending stops and the message becomes a draft again. A provider can also accept a text and block it later. Churchit cannot see that, so check the provider's log.

## Text replies and STOP

Churchit does not receive replies to texts: your text provider gets them. Use a provider that handles STOP replies itself. Twilio does this for numbers in the US and Canada. To change its keywords and reply, put the number in a Twilio Messaging Service, turn on Advanced Opt-Out and send your texts with that Messaging Service.

In other countries, and with other providers, read the provider's rules. When a person replies STOP, the provider blocks every later text to that number. The person replies START to get texts again.

Churchit does not know about a STOP reply, so it continues to send texts to that number, and each one shows Error. When a person asks to stop texts, record it: add a [Communication Consent](consent.md) for the person with the channel SMS and the status Withdrawn.

Leave Purpose blank to stop texts for all purposes. This applies to every text that Churchit sends: Church Emails, group messages, pages to parents at check-in, and serving requests and reminders. A message that also goes by email then reaches the person by email.

:::note[Example]
Mr. Smith replies STOP to a text about the picnic. His provider blocks the next text, and its copy shows Error. The office adds a Withdrawn SMS consent for him, and the next Church Email sent as text leaves him out.
:::

## Unsubscribe links

Every email has an unsubscribe link at the bottom, such as **Unsubscribe from Church News emails**. The person opens it and clicks **Unsubscribe** to confirm. They stop getting emails for that purpose only. Group messages, event reminders and pages from the Check-In Station keep coming. A member can change their choices on the **Preferences** page of the member portal. If a member stopped all emails from the church, the Preferences page says so, and turning on the Church News **Email** switch starts the emails again.

The Person form of someone who stopped all Church Emails shows **Unsubscribed from Church Emails** above the tabs. When someone without a portal login asks to get Church Emails again, open their Person and click **Actions**, then **Resubscribe to Church Emails**.

## Bounced Emails

When an email cannot reach an address, the mail server sends a report back to the church. This report is a bounce. Churchit reads bounces only when the church's email account also receives mail: open the Email Account that sends the church's email and tick **Enable Incoming**. Churchit reads the bounces of Gmail, Microsoft 365 and Postfix mail servers. It can miss a bounce from another mail server.

When a bounce says that delivery failed, Churchit ticks **Bounced** on that address on every record that has it, such as a Person or a Family. It does this only for an address that the church emailed in the last 7 days. A bounce for a full mailbox, a blocked message or a late delivery changes nothing. Church Emails skip a Bounced address, and the Person form shows an orange line: Email bounced.

:::tip
To find bounced addresses, open the [People Data Quality](../people/clean-data.md) report and set **Problem** to Email Bounced. Ask the person for a new address. When you change the address, Churchit clears Bounced. If you know that the old address works again, untick Bounced on that row.
:::

:::note[Example]
John's address has a typo, so the next Church Email bounces. Churchit ticks Bounced on his address, and later emails skip him. The office finds him on People Data Quality, calls him and corrects the address.
:::

## Who opened an email

When **Track Email Status** is ticked on the Email Account (it is by default), each copy shows **Read** on the timelines when the reader's mail app loads it. Many mail apps load nothing until the reader allows images, so fewer copies show Read than people who read the email.

Some mail apps, such as Apple Mail, load every email when it arrives, so a copy can show Read when nobody opened it. To stop this tracking, untick Track Email Status. If you keep it, mention it in the church's privacy notice.

## Email Templates

An Email Template is a ready-made Subject and Message. A System Manager adds templates. The **Template** list on a Church Email shows only the templates that use person placeholders, such as Birthday Greeting, New Member Welcome and Visitor Follow-Up. The other templates belong to features such as sign-ups, ministry teams and giving, which fill in their own placeholders. Do not use them for Church Emails, and change their placeholders with care.

## Email from the Person list

The Person list also has **Email** and **Email Household Adults** in its actions. These open your own mail app with the people in BCC. They do not check consent, add no unsubscribe link and keep no copy on the Person. For church news, use a Church Email.

## Draft with AI

When AI is turned on (see the [Foundations manual](../foundations/README.md)), some text fields have a **Draft with AI** link beside their label. The AI writes, shortens, changes the tone of or translates the text of that field:

- Church Email: Subject, Message and Text.
- [Bulletin](bulletins.md): Welcome Message and Announcements.
- Email Template: Subject and Response.
- [Function](../ministries/functions.md), Group and [Sermon Series](../study/sermons.md): Description.
- [Follow-up Workflow](../people/follow-up.md): the Text Message of a row in Actions.
- Web Page: Description in Meta Tags, and the alt text of pictures (see the [Website manual](../website/README.md)).

1. Click **Draft with AI** beside the field.
2. In **Action**, choose **Write**, **Shorten**, **Change Tone** or **Translate**. In **Request**, say what you want, for example "warmer" for Change Tone or "Spanish" for Translate.
3. Click **Draft** and read the suggestion.
4. Click **Use** to put it in the field, or close the window to keep your text.

Use changes only the form. Nothing is saved or sent until you save, and a Church Email goes out only when you click Send. A person can use Draft with AI 20 times an hour.

The AI gets your request, the text in the field, the name of your church and a few facts about the record, such as the name, date and place of a Function. It never gets a person, a prayer request or a gift.

For a saved Function that is not published, the AI model needs a Privacy Label of No training or better (see the [Foundations manual](../foundations/README.md)). An answer for a Church Email can use only the name placeholders. If an answer leaves out a placeholder that your text had, the window says so: put it back before you save.

The AI must not quote a Bible verse. It names a passage, and Churchit checks it: a sentence that names a passage that is not in the Bible is left out, and the window says so. Under **Bible passages**, the window shows the words from your church's default free translation. Check each passage in your Bible.

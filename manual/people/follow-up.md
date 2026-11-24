---
title: Follow-up
emoji: 🧭
sidebar_position: 17
---
Follow-up makes sure that each person who needs a next step gets one: a first-time guest gets a welcome call, a new member gets a coffee invitation, a person who asked about baptism hears from the pastor. A **Follow-up Workflow** is the list of steps, and a **Follow-up Card** is one person moving through those steps, on a board like sticky notes on a wall.

:::note[Example]
The Welcome workflow has three steps: Welcome Call (Sarah, 2 days), Coffee Invitation (the pastor, 7 days) and Connect to a Group (Tom, 14 days). When a guest's Connection Card arrives, a card opens at Welcome Call and Sarah gets a to-do and an email. After her call, she drags the card to Coffee Invitation, and the pastor gets the next to-do. When the guest has joined a group, Tom closes the card with the outcome "Joined Tuesday Bible Study".
:::

## Make a workflow

1. Open **Follow-up Workflows** and click **Add Follow-up Workflow**. Give it a name.

2. On the Details tab, add one row in **Steps** for each step, in order. In **Assign To**, choose who takes the step, and in **Due In (Days)**, how many days they have. A step with no user is assigned to nobody, and Churchit warns you when you save.

3. On the **Automation** tab, choose what starts a card (see below) and any actions.

4. Tick **Active** and save.

When you save, Churchit makes a board with a column for each step. Click **Open Board** to see it. You cannot remove a step while open cards are on it. Only Church Managers add and change workflows.

When AI is turned on (see the [Foundations manual](../foundations/README.md)), **Describe the Process** on a new workflow drafts the steps, triggers and actions from your words, such as "Call a first-time guest in 2 days, invite them for coffee after 5 days, and send a welcome email". Check the draft, pick Assign To for each step, and turn on Active when it is ready.

## Follow-up cards and the board

A Follow-up Card shows the person's phone and email, the step, and when it is due. A person can have only one open card on a workflow. When two records of one person are merged, only the older open card on each workflow stays open. To add a card by hand, open the person, go to Connections and click **+** next to Follow-up Card.

- **Move**: drag the card to the next column on the board, or open it and click **Move To**. The person of the new step gets a to-do and one email, and the due date starts again.

- **Snooze**: hides a card until a date, 7 days at first. It comes back by itself.

- **Close**: when the follow-up is done. Write what happened in **Outcome**. Closing also closes the to-do.

The Follow-up Cards list opens on the open cards, the soonest due first. Clear the Status filter to see closed cards. A card that a Connection Card started shows the interests the guest ticked and the guest's message as its reason.

## Start cards by themselves

On the Automation tab, under **Start a Card When**, add a row for each event that should start a card. Leave **Which** blank to start on any value, or choose one:

- **Connection Card**: a guest sends a card. Which is the interest they ticked.

- **First Check-In**: a person checks in for the first time ever (volunteer check-ins do not count). Which is the Function Type.

- **Signed Up**: a sign-up becomes Confirmed. Which is the Function Type. A card starts for each attendee who has a Person.

- **Form Submitted**: a person sends a form. Which is the Question Set.

- **Life Event Added**: a life event is added, for example a Baptism.

- **Membership Type Becomes** and **Member Status Becomes**: a person's membership or status changes to this value.

- **On Smart List**: once a day, everyone new on a saved list gets a card, each person only once.

- **Step Reached** and **Card Closed**: a card on another workflow reaches a step (type the **Step**, or leave it empty for every step) or closes. The new card shows the first card as its **Source**. A workflow cannot start itself, and it can start only from a workflow of the same church.

If the person already has an open card on the workflow, no second card starts. For a shared function or form, the person's own church does the follow-up.

:::note[Example]
When a Welcome card closes, you want new members to get a Membership Class card. Add a trigger **Card Closed** with Which set to Welcome on the Membership Class workflow.
:::

## Actions on a workflow

A workflow can do work by itself when a card opens, reaches a step or closes. On the Automation tab, add a row in **Actions**. In **When**, choose Card Opened, Step Reached (with its Step, or empty for every step) or Card Closed. In **Action**, choose:

- **Send Email**: choose a Purpose and an Email Template.
- **Send Text**: choose a Purpose and type the **Text Message**.
- **Add to Group**: choose a Group of your church.
- **Add Tag**: choose a Tag.

A message can use {{ first_name }}, {{ last_name }}, {{ display_name }}, {{ full_name }} and {{ step }}. A workflow with any other placeholder cannot be saved. A message goes only to a person who allows the Purpose, and a text only to a person who said yes to texts. Each action runs once for each card, event and step.

To see what ran, open the Connections tab of the workflow, or Follow-up Action Runs in the Setup folder. **Done** means the action ran, **Skipped** that there was nothing to do (for example the person has no address or is already in the group), and **Failed** shows the error. A failed action does not run again.

## Follow-up volunteers

Give a volunteer the **Church Follow-up Team** role profile. A volunteer sees only the cards assigned to them, on the board and in the list, and can move, snooze and close those cards. After they move or close a card, they can open it but not change it. After they sign in, the volunteer opens Follow-up Cards.

Church People Editor and Church Pastoral Care users add and change any card.

## Reminders and notices

- On any card, click **...**, then **Remind Me**, to get a reminder at a time you pick, or **Follow** to get an email when the card changes (turn on Send Notifications For Documents Followed By Me in your user settings).

- To email the person assigned to an overdue card, a Church Manager ticks **Email When a Follow-up Card Is Overdue** under Reminders in **People Settings**. **Days After the Card Is Due** sets when (1 day at first). Snoozed cards get no email.

- The shipped **Visitor Follow-Up** notification can email the Church Managers about each new visitor (see [Notifications](../communications/notifications.md) in the Communications manual).

## AI suggestion on a new card

When AI is turned on and a Church Manager has turned on suggestions on new requests (see the [Foundations manual](../foundations/README.md)), a new card that a Connection Card or a form started gets a comment **AI suggestion**: which workflow fits, why, and a first email. Click **Draft the Email** to open a new Church Email to the person, not saved: read it, change it and send it yourself. AI never moves the card or sends a message.

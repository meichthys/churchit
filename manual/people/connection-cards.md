---
title: Connection Cards
emoji: 🙋
sidebar_position: 16
---
A Connection Card is the welcome card that a guest fills in on their phone, at `/connection-card` on your website. They give their name, email and phone, say whether they are new, tick what they would like to do next, and add the people who came with them. Churchit then adds them to People and starts their follow-up, so that no guest is forgotten.

:::note[Example]
On Sunday, the Lees scan the QR code in the bulletin and fill in a card: Daniel and Grace Lee, with their son Sam, age 7, and a tick on "Join a group". Churchit adds the three as Visitors in one Lee family, and starts a follow-up card on the Welcome workflow and on the Groups workflow. On Monday, the welcome volunteer sees the card on her board and calls them.
:::

## What happens to a card

After a guest sends a card, Churchit looks for them in People:

- If one person has the same email or phone and the same first and last name, the card is linked to that person. Churchit does not change that person's details, and does not add the people who came with them.

- If not, Churchit adds the guest as a new person with the Membership Visitor and the Source Connection Card, with **How They Heard** from the card. Close matches go to Possible Duplicates for you to check.

- Then each follow-up workflow that starts on a Connection Card opens a follow-up card for the person (see [Follow-up](follow-up.md)).

The list shows each card's status: **New** until Churchit finds or adds the person, **Processed**, or **Spam**. On a processed card, **Person** opens the person it was linked to or added, and Connections shows the follow-up cards it started. Church Manager and Church People Editor users can also add a card in the desk from a paper card, and Churchit handles it the same way.

## What guests can tick

The boxes under **I Would Like To** come from the Connection Card Interest list: Join a group, Serve on a team, Learn about baptism, Learn about membership and Talk with a pastor at first. You can rename, delete or add your own. To start a workflow when a guest ticks one, add a Connection Card trigger with that interest to the workflow.

The **Stay in Touch** boxes, **Email Me Church News and Events** and **Text Me Church News and Events**, record the guest's yes to Church News (see [Consent](../communications/consent.md) in the Communications manual).

## Who came with the guest

In **Who Is With You?** a guest can add the people who came with them: name, relationship and birth date. When Churchit adds the guest as a new Visitor, it makes a family with the guest as the Primary Contact, and adds each of these people to it as a Visitor.

A person with no last name gets the guest's last name. A Wife or Husband becomes the guest's spouse. A birth date becomes a Birth life event, so the family can set each household role.

## Print a QR code for the form

Open the Connection Card web form and click **QR Code**. With more than one church, choose the church that the cards are for. Click **Download** to save the code for your bulletin or welcome card. Every published web form has this button, so you can do the same for the prayer request form.

## Spam and busy Sundays

The form has a box that people never see but robots fill in. A card with that box filled in gets the status Spam and adds nobody. If a real guest's card was marked Spam, add the person yourself.

Each internet address can send the form at most 10 times a minute. On a busy Sunday, guests on the church Wi-Fi share one address. A guest who sees "too many requests" can send the card again a minute later.

## Paper connection cards

For a paper card, add a photo of it and type the card from the photo:

1. Open **Connection Card Photos** (Card Photos in the sidebar) and click **Add**. You need the Church People Editor or Church Manager role.
2. Attach one clear photo of one card, taken from above, and save. The photo is a private file.
3. Click **Copy by Hand**. A new Connection Card opens with the photo at the top. Type what the card shows and save. The photo then shows Imported, and the follow-up starts as for any card.

When AI is turned on (see the [Foundations manual](../foundations/README.md)) and the site has Flow, AI reads the photo into a draft instead. The status goes from **Waiting** to **Reading** to **Ready to Check**. Compare each value of the draft with the photo, because AI can misread handwriting, then click **Create Connection Card**, correct the card and save it.

AI never ticks Email Me or Text Me, and adds no person by itself. When AI cannot read a photo, the status is **Failed**: click **Actions**, then **Read Again**. A card holds children's names, so AI reads a photo only with a model that keeps no copy of your data. When AI is off, a new photo is **Ready to Copy**.

Delete a photo that you do not use when you are done with it. Deleting a Connection Card deletes its photo too.

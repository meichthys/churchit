---
title: Send records to other systems
emoji: 🔗
sidebar_position: 6
---
This part is for a System Manager. Churchit can send a record to another system when someone adds or changes it, for example to a mailing tool or a chat room, with no custom code.

**Never send care, medical, pickup or giving fields to another system.** The other system does not protect them as Churchit does, and it does not follow your church and consent rules.

## Send a record with a Webhook

Open [Webhooks](/desk/webhook) and add one:

1. Set **DocType** to the record to send, such as Person or Connection Card, and **Doc Event** to when it goes, such as after_insert for a new record.

2. Set **Request URL** to the address that the other system gives you.

3. Tick **Enable Security** and type a **Webhook Secret**. Give the same secret to the other system, so that it can check that each request came from your site.

4. Set **Request Structure** to JSON. In **JSON Request Body**, put only the fields that the other system needs, for example {"first_name": "{{ doc.first_name }}"}.

5. With more than one church, type doc.church == "CHURCH-ID" in **Condition**, with the ID of the church. Then only that church's records go.

A request that fails is kept in the Webhook Request Log.

## Send an alert to a chat room

Frappe sends alerts to Slack, and Mattermost accepts the same alerts:

1. In the chat app, make an incoming webhook and copy its address.
2. Find **Slack Webhook URL** with the search bar, add one with a **Name**, and paste the address in **Webhook URL**.
3. Open [Notifications](/desk/notification) and add one. Set **Channel** to Slack, choose the webhook in **Slack Channel**, and set **Document Type**, **Send Alert On** and **Message**.
4. With more than one church, type doc.church == "CHURCH-ID" in **Condition**.

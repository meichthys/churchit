---
title: Rooms
emoji: 🚪
sidebar_position: 1
---
A Room is a space that people can book, such as the sanctuary, a classroom or the fellowship hall. Each room has its own booking rules: who approves its bookings, how it can be set up and what to ask the person who books it.

:::note[Example]
The fellowship hall holds 120 people. It can be set up as Banquet (tables for 64) or Theatre (rows of chairs). Bookings need approval from the facilities manager, and each booking must say how many guests will come and whether they need the sound system.
:::

## Add a room

1. Open **Rooms** and click **Add Room**.
2. Type the **Room Name** and pick its **Location**, such as the building it is in.
3. Fill in the **Capacity**, the number of people it holds.
4. Set the booking rules (see below) and save.

A new room is **Bookable**. Untick Bookable for a room that people may not book, such as the church office. Bookings of a room that is not bookable are refused.

**Capacity** does more than inform. When a Function books the room, check-in can stop at the room's capacity (see the [Ministries manual](../ministries/README.md)). The **Book a Room** dialog on a Function shows the capacity of each room. Leave Capacity empty for no limit.

Each church gives its rooms their own names, so two churches can each have a room called Sanctuary. One church cannot have two rooms with the same name. The **Bookings** and **Work Orders** sections at the top of a room show its bookings and the work orders that name it. You cannot delete a room that a booking or a task names.

## Approval and approvers

In the **Booking Rules** section:

- **Requires Approval**: tick it when someone must approve each booking. Without it, every booking is approved at once.

- **Approvers**: the users who approve the bookings of this room. Each approver needs the Church Staff or Church Manager role and access to the church of the room. When the table is empty, the Church Managers of the church approve.

## Setups

Add the ways that a room can be set up, such as Banquet or Theatre, in the **Setups** table. Give each setup a name that the room does not use yet, and add the capacity, a description and a photo if you want. A booking can then choose one of these setups (see [Room Bookings](room-bookings.md)). If you remove a setup from a room, the bookings that already use it keep it.

## Questions

To ask each booking of a room some questions, such as the number of guests or the need for sound, choose a [Question Set](../ministries/question-sets.md) in **Question Set** (see the [Ministries manual](../ministries/README.md) for Question Sets). A room can use a Question Set of your church or a shared one.

When someone chooses the room on a booking, the questions open in a dialog. Click **Done** to keep the answers. To change them later, click **Answer Questions**. A booking cannot be saved until each required question has an answer.

- If you move a booking to a room with other questions, the old answers are removed and you answer the new questions.

- If you change the Question Set of a room, its bookings keep their old answers until someone answers again with **Answer Questions**.

- Members cannot book a room that has a required question in the member portal, and the Book a Room button on a Function does not offer a room with a Question Set. Book these rooms on the Room Booking form.

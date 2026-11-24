---
title: Room Bookings
emoji: 📅
sidebar_position: 2
---
A [Room Booking](/desk/room-booking) reserves a room, equipment or both for a time. Churchit makes sure that two bookings never hold the same room or the same equipment at the same time.

Click **Room Bookings** in the sidebar to open the calendar of bookings by month, week or day. Click a booking to open it. The calendar does not show Denied and Cancelled bookings: remove the Status filter to see them. To see the bookings as a list, click **Calendar View** at the top and choose **List View**. To find a booking by its number, such as BK-0012 on a setup sheet, type it in the **ID** box of the list.

## Book a room

1. Open [Room Bookings](/desk/room-booking) and click **Add Room Booking**. Your own name is filled in as the **Requester**. The Requester must be a person of the church that books the room.

2. Fill in the **Purpose**, then choose the **Room**. Only bookable rooms are offered. Answer the room's questions if a dialog opens.

3. Fill in the **Start** and the **End**. The Purpose shows on the calendar.

4. To ask for a setup, open the **Setup** section, choose one of the room's setups and add **Setup Notes** for the people who set up the room.

5. Save.

Church Staff can read all bookings of their church, and add and change their own. Church Managers can change every booking.

## Approval

On a room that does not require approval, a new booking is **Approved** at once. On a room with **Requires Approval** ticked, a new booking is **Requested** until an approver decides. A booking that an approver of the room makes is approved at once.

Each approver gets a To Do for each Requested booking, with the room, the purpose and the time. The approver opens the booking and clicks **Actions**, then **Approve** or **Deny**. The To Dos close, and the person who made the booking gets an email with the decision and a link to the booking. When staff book a room for someone else, the staff member gets this email, not the Requester.

If someone who is not an approver changes the room, the start or the end of an approved booking, it goes back to Requested and waits for approval again. A change to the notes keeps it approved.

Other statuses: **Cancelled** frees the room, and anyone who may change the booking can set it. **Completed** marks a booking that is over. A Denied booking can be opened again only by an approver.

## When two bookings clash

Two bookings of one room cannot overlap. When a new booking clashes, Churchit refuses it and names the bookings in the way, with their purpose and time. It counts the bookings of other churches but does not name them.

If you still need the room, tick **Request Anyway** in the **If the Room Is Taken** section and save. The booking gets the status **Conflict**, and each approver gets a To Do. A Conflict booking does not stop other people from booking the room. The approver opens it and clicks **Actions**, then one of these:

- **Keep This Booking** approves it and denies the Requested and Conflict bookings that it clashes with. It shows only when no Approved or Blocked booking holds the room at that time.

- **Share the Room** ticks **Can Share Room** on it and on each booking that it clashes with, and approves it. Two bookings that both have Can Share Room ticked do not clash.

- **Deny** denies it.

**Example:** The youth group's booking of the fellowship hall on Tuesday at 7 PM is Approved. The women's Bible study then needs the same hall at the same time, so its leader ticks Request Anyway. The pastor opens the Conflict booking. The hall is big enough for both groups, so the pastor clicks Share the Room: the Bible study's booking is approved, and both groups use the hall. If the youth booking were still Requested, the pastor would approve it too.

## Block a room

To keep a room free, for example for repairs or a holiday, an approver of the room adds a Room Booking with the status **Blocked**. It needs no Requester. When the room has no Approvers, a Church Manager blocks it.

- When you save a blocked time, each Requested or Conflict booking at that time is denied.
- An Approved booking at that time stops the block from saving. Cancel or move that booking first.
- Nobody can book a blocked time, also not with Request Anyway.
- Only an approver of the room (or a Church Manager when the room has no approvers) can change or remove a blocked time.

**Example:** The sanctuary floor is refinished in the first week of March. The facilities manager blocks the sanctuary for that week. Two requests for that week are denied at once, and nobody can ask for it again until the block ends.

## Book equipment

To book a [Church Asset](/desk/church-asset), such as a projector or the church van, first tick **Bookable** on the asset. Then choose it in **Equipment** on a Room Booking. Leave **Room** empty to book only equipment. A booking of equipment only is approved at once and belongs to your church.

Equipment can be in only one booking at a time, and a Conflict booking holds its equipment too. If another booking has the equipment at that time, Churchit refuses the booking and names the other one.

## Lend equipment

Use a Room Booking with only equipment to lend something to a person.

1. Add a Room Booking, choose the equipment in **Equipment** and leave **Room** empty.
2. When the borrower takes the equipment, open the booking and click **Actions**, then **Check Out**. **Checked Out On** shows the time.
3. When the borrower brings it back, click **Actions**, then **Check In**. **Returned On** shows the time, and the status changes to Completed.

Only Church Manager and System Manager users can check equipment out or in, and nobody can type these times by hand. You cannot check out equipment that is still out on another booking: check in that booking first. A Completed booking does not hold its room or its equipment.

The [Assets on Loan](/desk/query-report/Assets on Loan) report shows all equipment that is out and not returned. The booking with the oldest End is at the top, so late returns show first.

**Example:** Deacon Smith borrows the projector for a weekend retreat. The office books the projector from Friday to Monday with no room and clicks Check Out when he picks it up. On Tuesday the projector is still not back, so it is at the top of Assets on Loan. When he returns it, the office clicks Check In.

## Rooms for a Function

To book rooms for a [Function](/desk/function), open the Function and click **Actions**, then **Book a Room**. Choose one or more rooms and any equipment, check the Requester and the times, and click **Book**. Each room gets its own booking, and the equipment goes with the first booking that saves.

- When a Function is deleted, its bookings are deleted too.

- A recurring Function copies the Requested and Approved bookings of its first Function to each new one. A copy that clashes becomes a Conflict. A copy that cannot be saved, for example in a blocked time, is skipped, and a comment on the new Function says so.

- The public church calendar shows the rooms of a Function's approved bookings.

## Room requests from members

Members ask for a room on the **Book a Room** page of the member portal (it opens at /portal/room-request). A member clicks **Ask for a room**, chooses a room, the start and the end, says what it is for, and can add notes.

- The page offers only the bookable rooms of the member's church and the shared rooms, and not a room with a required question.

- The member is always the Requester. A member can ask only for a time that has not passed, and for one day at most. For a longer booking, the member asks the church office.

- Members cannot book equipment, and a request that clashes is refused. Staff add equipment to the booking if needed.

- On a room that requires approval, the request stays Requested until an approver decides, and the member gets an email with the decision.

- The page lists the member's own requests with the room, the time and the status. A booking that staff made for the member does not show there. A member can change a request that is still to come, unless it was denied, cancelled or completed. Only staff can cancel it.

If your portal menu does not have **Book a Room**, open [Portal Settings](/desk/portal-settings) and add a row to **Menu** with the Title Book a Room, the Route room-request, the Reference Document Type Room Booking and the Role Church User.

## Setup sheets

To give the people who set up a room what they need, open the Room Booking, click **Print** and choose **Setup Sheet**. The sheet shows the room, the times, the purpose and the requester, the setup with its capacity and description, the setup notes, the equipment and the answers to the room's questions. Print it or click **Get PDF**.

## Reports

- [Room Usage](/desk/query-report/Room Usage) (in the Reports folder) shows how your rooms and equipment are used: one row for each booking in the dates you choose, with the hours. It opens on the current month and lists every status, also Denied and Cancelled, until you choose a Status. You can also filter by Room. Church Managers and Church Staff can open it.

- **Booking Requests** (the shortcut on the workspace) lists the Requested and Conflict bookings, the soonest first.

- **Assets on Loan** is described under Lend equipment.

## Rooms with more than one church

A room belongs to one church, and only that church can book it. Tick **Shared with All Churches** on a room to let every church book it. A shared room has one calendar for every church: every church sees its bookings, and a booking blocks that time for all of them. The name of a shared room must differ from every other room. You see the bookings of your churches and of the shared rooms.

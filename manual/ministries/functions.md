---
title: Functions
emoji: 🗓️
sidebar_position: 2
---
A [Function](/desk/function) is one service, meeting or event: Sunday Worship on November 15, the Tuesday Bible study, the church picnic. Everything about the event hangs on it: the order of service, the people who serve, the sign-ups, the room bookings, the bulletin, the collection and the attendance.

**Example:** For Sunday Worship, the office adds a Function for Sunday at 10:00. On the Service Plan tab, the worship leader lists the songs and the sermon. The ministry team schedule asks three greeters and a sound technician to serve. On Sunday, volunteers check the children in at the Check-In Station, and the counters enter the offering in a Collection for this Function. On Monday, the Attendance Total shows who came.

## Add a function

1. Open [Functions](/desk/function) and click **Add Function**.
2. Type the name, choose the **Type** (such as Sunday Morning Service or Group Meeting) and the **Associated Ministry**, and set the **Start Date**, **Start Time** and **End Time**. Add the address if it is not at the church.
3. To show it on the public website, tick **Publish** in the **Website and Streaming** section.
4. Save.

Churchit refuses an end before the start, an Online Meeting Link that does not start with https:// or that has a space, sign-ups that close before they open, a Repeat Until before the Start Date, a Minimum Age above the Maximum Age, and a Minimum Grade above the Maximum Grade.

The form has five tabs:

- **Details**: what, when and where, the **Website and Streaming** settings, the **Recurrence** and the **Associations** (other records that the function is about).
- **Service Plan**: the **Schedule** (the order of service) and the **Team Needs** (the people who must serve).
- **Registration**: the sign-up settings (see Function Sign-Ups).
- **Attendance**: the attendance total, the headcount, the attendance rows and **Who Can Check In**.
- **Connections**: the sign-ups, check-ins, team assignments, room bookings, bulletins, meeting minutes and collections of the function.

Under **Actions** on a saved function are **Check-In Station**, **Book a Room**, **New Bulletin**, **Email the Team** and **Fill Open Needs**. Under **View** are the **Team Schedule**, **Signed-Up Items** and **Signed-Up People** reports. Each one shows only to the users who may use it.

## Function types and templates

Churchit starts with function types such as Sunday Morning Service, Prayer Meeting, Communion, Baptism and Group Meeting. You can add more under [Function Types](/desk/function-type) in the Setup folder.

A function type can name a **Template Function**: an earlier function whose details you want to copy. On a new function of that type, set the Start Date first, then click **Fill From Template**. Churchit copies most details, the schedule (moved to the new date, at the same times) and the attendance rows.

## Plan the service

Plan the order of a service in the **Schedule** table on the Service Plan tab. Each row has a **Start** time. Tick **Header** on a row to make it a heading for a part of the service, such as Worship or Response. The bulletin prints the schedule as its Order of Worship.

- A row can link a [Song](/desk/song), a [Sermon](/desk/sermon), a [Person](/desk/person) or another record. For a song, choose the **Arrangement** and the **Key**. Leave the Key empty to use the key of the arrangement, or the song's default key. A row whose Arrangement is not one of the song's arrangements cannot be saved.

- **Displayed** (ticked at first) and **Printed** record how the words of a song were copied. Tick **Streamed** or **Recorded** on the function when the service went out live or was recorded. The Song Usage report counts these uses for your CCLI report.

- **Team Notes** are for the people who serve only. They see them on the **Serving** page of the member portal. The bulletin never prints them.

## On the website

- **Publish** shows the function on the public [Calendar](/calendar) page and in the calendar feed. A function over several days shows on each day. Visitors click it to see the time, the address with an **Open map** link, the rooms of its approved bookings, and the links below.

- **Link Only** keeps a published function off the Calendar page, the feed, the home page and the Register list. Share its link instead, such as /calendar?event=FUNC-0042, or a Register link with ?function=FUNC-0042. Function IDs are numbers in order, so a person can guess the link: do not use Link Only to keep a private event secret.

- **Online Meeting Link**: an https link to join online, such as a video call. The Calendar shows **Join online**, and the link is in the calendar feed, on the Serving page and in a sign-up's calendar file.

- **Streamed**: when your church has a Live Stream Link (see Watch Live in the Website manual), the Calendar shows **Watch live** on the function from 15 minutes before it starts until it ends.

- With more than one church, the Calendar of a church with published branch churches offers **Include branch churches**.

## Attendance

Record who came on the **Attendance** tab. Add a row for each person with an attendance type, or click **Add Multiple** under the table to add many people at once, for example from a sign-in sheet. Check-ins and sign-ups add their rows by themselves. A person can be on only one row.

**Attendance Total** counts only the rows whose type is **Confirmed**, **Assumed** or **Checked-In**. Signed-Up and Absent rows do not count, and neither does a type that you add yourself under Attendance Types. A function counts its attendance only from its Start Date, so rows that you add ahead of time, for example from a roster, count once the day comes. Each day, Churchit updates the totals of the functions of the last week.

**Headcount** is the number of people in the room, named or not (see Headcount under Check-In Station).

Several people can change attendance at once: a check-in, a sign-up and a member's change in the portal each change only that person's row. A sign-up never replaces a row that says more, such as Checked-In or Absent. If someone checks a person in while you have the function open, your save stops and asks you to reload, so no row is lost.

**Sign-in sheet.** Print (Ctrl+P) on a function opens the **Attendance Sign-In Sheet**, with each person and their household, such as John & Jane Smith, and Yes under Visitor? for visitors. Guests of a confirmed sign-up who have no Person record get a row too.

## Attendance in the member portal

Members see their own attendance on the **Attendance** page of the member portal. **Attended** lists the functions up to today that have them in the attendance, with the type. **Coming up** lists the functions after today that they signed up for, with the status of the sign-up.

To let members correct their own attendance, tick **Members Can Change Their Attendance** in [Portal Settings](/desk/portal-settings). Each Attended row then offers **I was there** (saved as Confirmed) and **I was not there** (saved as Absent), and the total follows. A Checked-In row can be changed only in the desk.

## Find functions and reports

- **Coming Up This Week** shows the functions of the next days first. The Functions list shows the newest dates first, so a service today can be far down the list.

- When a form asks for a Function, such as a Bulletin or a Collection, the list shows the functions from today on first, then the past ones.

- **Church Calendar** opens the calendar of functions. A function with **All Day** ticked, or with no Start Time, shows in the all-day row, and one with no End Time shows as one hour long. Drag a function to move it to another day or time, or drag its lower edge to change the end. The schedule rows and the room bookings do not move with it.

- The attendance reports are in the **Attendance** folder: Church Attendance (the last four weeks at first), Check-Ins by Function, Attendance by Person (the last three months at first) and Function Count by Type. The first three have a **Group** filter to see only the meetings of one group.

- The **Function Planning** folder holds the sign-up reports, the Recurring Functions report and the Functions Report.

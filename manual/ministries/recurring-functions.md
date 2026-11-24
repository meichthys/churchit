---
title: Recurring Functions
emoji: 🔁
sidebar_position: 3
---
Most church events repeat: the Sunday service every week, the women's Bible study every other Tuesday, the elders' meeting on the first Monday of the month. Set up the function once, and Churchit makes each occurrence for you.

The function that you set up is the **template**. A template is a rule, not an event: it does not show on the calendar, nobody checks in to it, and no report counts it. Churchit makes the occurrences from it, each one a normal Function that copies the template's schedule, team needs, associations, sign-up settings, discounts and attendance roster. Requested and Approved room bookings move to the new date too.

**Example:** The youth group meets every Wednesday at 7 PM in the fellowship hall. You make one Function, Youth Group, with Automatically Recreate ticked, Weekly on Wednesday, and a room booking. Churchit makes the next eight Wednesdays at once, each with its own booking of the hall. Before Christmas, you add the Wednesday of Christmas week to Skip Dates, so there is no meeting that week.

## Make a function repeat

1. On the [Function](/desk/function), open the **Recurrence** section and tick **Automatically Recreate**.

2. Choose a **Repeat Frequency**: Daily, Weekly, Monthly or Yearly. In **Repeat Every**, type 1 for every time, or 2 for every second day, week, month or year.

3. For Weekly, choose the day in **Repeat Day of Week**.

4. For Monthly, choose **Repeat Monthly By**. With **Day of Month**, type the day, such as the 15th (a day after the end of a short month moves to its last day). With **Weekday**, choose the week and the day, such as the **Second Sunday** or the **Last Friday**.

5. If you want, set **Repeat Until** to stop on a date.

6. Save.

You can also open a [Ministry](/desk/ministry) and click **Create Recurring Function** to start one that belongs to that ministry.

## How occurrences are made

- Churchit makes the first occurrences a moment after you save the template. Each day, it makes the next ones ahead of time, for the number of weeks in **Create Weeks Ahead** (8 at first), so they show on the calendar early.

- The people in the template's Attendance table are a roster. Each occurrence copies them, except people who have died. They count as attendance only once that occurrence starts.

- The sign-up open and close dates and the discount dates move with each occurrence's start date.

- A change to the template reaches only the occurrences that Churchit makes after the change. To change occurrences that already exist, edit or delete them.

- Add a date to **Skip Dates** when the function does not happen on that day. When you delete an occurrence, its room bookings are deleted and its date is added to Skip Dates, so it is not made again.

- If a room is already booked at the new time, the occurrence is made without that booking, and a comment on it names the room and the time. A room that needs approval gets a Requested booking.

- Untick **Automatically Recreate** at any time to stop.

## Group meetings

A Function can be a meeting of a [Group](/desk/group), such as a small group or a class. Choose the group in the **Group** field of the function, not in Associations. The group must belong to the church of the function, and a function with a group cannot be shared with all churches.

To give a group a weekly or monthly meeting, open the group and click **Actions**, then **Set Up Meetings**. A new Function opens with the group, the type Group Meeting and Automatically Recreate ticked. Choose the day, the time and the address, and save. Record the attendance on each meeting, not on this schedule.

**Attendance reminder.** The day after a group meeting with no attendance recorded, Churchit emails the group's leaders a link to record it in the member portal. It sends nothing when the site has no outgoing email account.

**Did Not Meet.** When a group did not meet, tick **Did Not Meet** on the Attendance tab of that meeting. Churchit then sends the leaders no reminder, and the Group Attendance report does not count it. A leader can also do this in the member portal (see Lead a Group in the People manual). **Attendance Recorded On** shows when a leader last saved the attendance.

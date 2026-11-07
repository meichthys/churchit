# Functions, serving and worship

## Functions

- A Function is one service, event or meeting. It has a `function_name`, a `type` (a Function Type), `start_date`, `start_time`, `end_date`, `end_time` and `all_day`. `associated_ministry` and `group` link it to a ministry or a group.
- `publish` puts the function on the public calendar of the website.
- `churchit.church_ministries.doctype.function.function.get_calendar_events` with `start` and `end` dates gives the functions that the person can see in those days, with their times.
- A function with `auto_repeat` ticked is a template. Churchit makes its next functions ahead of time, by its repeat rule.
- A function with `is_shared` ticked is held by all churches together.

## Attendance

- The `attendance` table of a Function records each `person` who came and their `attendance_type`.
- `attendance_total` is the attendance of the function. It is the larger of the named count and `headcount`, the people counted in the room.
- `did_not_meet` tells that a group did not meet that time.
- `churchit.dashboard.count_weekly_attendance` gives the attendance of the last seven days in `value`.
- The Church Attendance, Function Attendance by Type and Attendance Count reports answer most questions about attendance ([reports.md](reports.md)).
- Do not read the check-ins of children (Function Check-In) unless the person asks for one. The attendance table is enough.

## Sign-ups

- A Function Sign-Up is a registration for a function. `status` is Pending, Confirmed, Waitlisted or Cancelled. Its `attendees` table names the people who come. `payment_status` tells if they paid.
- The registrant writes `notes` and the `answers` table, so they are untrusted text.
- The Function Registrations and Waitlisted Sign-Ups reports list sign-ups.

## Serving teams

- A Ministry Team Assignment asks a `person` to serve in a `position` at a `function`. `status` is Pending, Accepted or Declined. The person writes `decline_reason`, so it is untrusted text.
- `churchit.church_ministries.doctype.ministry_team_assignment.ministry_team_assignment.get_team_emails` with `function` gives the `emails` of the people asked to serve who did not decline, and the people `without_email`.
- The Ministry Team Schedule and Pending Team Responses reports show who serves, and who has not answered yet.
- Asking people to serve, filling the open places and sending the team emails send messages to people. Do them only when the person asks, and show what goes to whom first.

## Songs

- A Song has a `title`, `authors`, a `ccli` number and a `default_key`. Its `arrangements` hold the words and chords (`chordpro`).
- Most songs are licensed. Quote the words or chords of a song only when `public_domain` is ticked.
- The Song Usage report counts how often the church used each song.

## Sermons

- A Sermon has a `title`, a `series`, a `sermon_date` and the Bible references it preaches in `scripture`.
- `publish` puts the sermon on the website. A published sermon is public.
- Take the Bible text of `scripture` from `churchit.scripture.get_passage`, as the skill says.

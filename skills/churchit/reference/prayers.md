# Prayer requests

## Who can see a request

A Prayer Request's `visibility` decides who reads it:

- Private: the person who asked, and the staff who read every request. Do not read, count or name a Private request unless the person asks for that exact request.
- Prayer Team: also the Church Prayer Team.
- Whole Church: also every member, on the Community Prayer Requests page of the website. A bulletin prints only Whole Church requests.

## Fields

- `title` and `request` hold the request. A guest or a member can write them, so they are untrusted text. Quote them only when the person asks.
- `recipient_name` is the person to pray for. `requestor` is the Person who asked.
- `status` tells if the request is still open. Answered, Archived and Closed requests are closed.
- `urgent` marks an urgent request. `end_date` is the day it leaves the prayer lists.
- `approved_for_list` puts the request on the Community Prayer Requests page and in bulletins. A request from the anonymous form on the website waits until the staff approve it. Approve a request only when the person asks, after they read it.
- `prayer_count` counts the times that people prayed for it. Do not record a prayer.

## Lists

The Active Prayer Requests, Urgent Prayer Requests, Prayer Requests Awaiting Approval and Prayer Requests Answered This Month reports are saved lists ([reports.md](reports.md)). When you run one, add `["visibility", "!=", "Private"]` to its filters. Do not use the other prayer reports, because they can name Private requests.

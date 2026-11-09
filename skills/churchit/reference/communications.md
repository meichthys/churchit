# Communications

Sending a Church Email, a text, an email from a form or a message to a group reaches real people and cannot be undone. Write the message in your answer first. Send it only when the person says yes, or let the person send it from the desk.

## Church Emails

- A Church Email is one message to many people. `channel` is Email or Text Message. `status` is Draft, Scheduled, Sending or Sent.
- `send_to` chooses the people: Active People, Active Members, Group, Smart List or Chosen People. `include_household` adds their households.
- A message can use these placeholders, which Churchit fills in for each person: `{{ first_name }}`, `{{ last_name }}`, `{{ display_name }}` and `{{ full_name }}`. Use no other placeholder.
- To help the person send one, draft it with `churchit.ai.drafts.propose` for `Church Email`: `channel`, `subject`, `message` (or `text_message` for a text), `send_to` and, for the people, `group`, `smart_list` or `people`. The draft never sets `status` or `send_after`, so the message stays a draft. The person opens the link, checks the text and the people, and clicks Send. Say who it goes to, and never send it yourself.
- A smart list for a Church Email is a saved smart list. To make one from a sentence, see [people.md](people.md).
- The Scheduled Emails report lists the messages that wait to go ([reports.md](reports.md)).

## Consent

- A Communication Consent records a yes (`status` Given) or a no (`status` Withdrawn) of a person, for a `channel` (Email, SMS, Push, Phone or Post) and a `purpose`.
- Churchit sends a message only to the people who allow it. A Church Email leaves out everyone else.
- Change consent only when the person asks for that exact change. When someone asks to start or stop church messages, tell the person, and record it after they say yes.

## Bulletins

- A Bulletin is the handout of one function, with `welcome`, `announcements`, a `verse` and the prayer requests that staff chose.
- Write the text of a bulletin in your answer. Save it only when the person says yes.
- A Bible reference in a bulletin follows "Bible text" in the skill.

## Email Templates

An Email Template is a starting text for an email. `list_documents` on Email Template gives them. A template writes the placeholders of a Church Email in Frappe's form, such as `{{ doc.first_name }}`.

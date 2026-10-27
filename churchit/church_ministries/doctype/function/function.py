# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from datetime import datetime, time, timedelta

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, cint, date_diff, flt, format_datetime, get_datetime, getdate, validate_url

from churchit.church_ministries.attendance import get_attendance_total
from churchit.church_ministries.sign_up_amounts import is_freely_given
from churchit.church_scope import refuse_another_churches_fund, refuse_another_churches_record
from churchit.utils import link_title

TIME_FORMAT = "h:mm a"


class Function(Document):
	def validate(self):
		# Only the recurrence job links an occurrence, so a user cannot write into another template.
		if (
			self.source_template
			and self.has_value_changed("source_template")
			and not self.flags.ignore_permissions
		):
			frappe.throw(_("Only the recurring functions job sets Source Template."), frappe.PermissionError)

		self.refuse_new_group_associations()
		if any(self.has_value_changed(field) for field in ("group", "church", "is_shared")):
			self.validate_group()
		self.refuse_another_churches_question_set()
		self.refuse_another_churches_sign_up_fund()
		self.validate_meeting_url()
		self.validate_schedule_songs()

	def on_update(self):
		self.promote_waitlist_when_capacity_grows()
		self.settle_payment_holds_when_prices_change()

	def validate_meeting_url(self):
		"""Guests open the meeting link, and a URL field accepts javascript:, so it must be https.

		Calendar feeds write the link as it is, so a space or a line break in it is refused too.
		"""
		if not (self.meeting_url and self.has_value_changed("meeting_url")):
			return
		self.meeting_url = self.meeting_url.strip()
		if any(character.isspace() or not character.isprintable() for character in self.meeting_url):
			frappe.throw(_("The Online Meeting Link must not contain spaces or line breaks."))
		validate_url(self.meeting_url, throw=True, valid_schemes=("https",))

	def validate_schedule_songs(self):
		"""A Song row names a song the editor may read, and an arrangement of that song.

		Only new and changed rows: an attendance save must not trip on a song edited since.
		"""
		if self.is_new() and self.source_template:
			# The recurrence job copies the template's rows, checked when the template saved.
			return

		before = self.get_doc_before_save()
		rows_before = before.schedule if before else []
		stored = {row.name: (row.item_type, row.item, row.arrangement, row.song_key) for row in rows_before}
		for row in self.schedule:
			if row.item_type != "Song" or not row.item:
				continue
			if stored.get(row.name) == (row.item_type, row.item, row.arrangement, row.song_key):
				continue
			# Before the song is read: its media reach this Function's team.
			if not frappe.has_permission("Song", "read", doc=row.item):
				frappe.throw(
					_("Schedule row {0}: you cannot use this song.").format(row.idx), frappe.PermissionError
				)
			self.set_schedule_song_key(row, stored.get(row.name))

	def set_schedule_song_key(self, row, stored_row: tuple | None):
		"""Refuse an arrangement *row*'s song does not have, and fill the key from it or the song."""
		song = frappe.get_cached_doc("Song", row.item)
		arrangement = next(
			(option for option in song.arrangements if option.arrangement_name == row.arrangement), None
		)
		if row.arrangement and not arrangement:
			frappe.throw(
				_("Schedule row {0}: {1} has no arrangement named {2}.").format(
					row.idx, frappe.bold(song.title), frappe.bold(row.arrangement)
				)
			)

		# A key left as it was while the song or arrangement changed belongs to the old one.
		if stored_row and stored_row[1:3] != (row.item, row.arrangement) and stored_row[3] == row.song_key:
			row.song_key = None
		if not row.song_key:
			row.song_key = (arrangement.song_key if arrangement else None) or song.default_key

	def refuse_another_churches_question_set(self):
		"""The sign-up questions come from a Question Set of this church or a shared one."""
		# Only when they change: an attendance save of the Function must not trip it.
		if any(self.has_value_changed(field) for field in ("question_set", "church", "is_shared")):
			refuse_another_churches_record(self, "Question Set", self.question_set)

	def refuse_another_churches_sign_up_fund(self):
		"""Sign-up payments go to a fund of the payment church or a shared one, and a price needs a fund.

		A function that is freely given for good takes no payment, so it needs none.
		"""
		priced = any(flt(row.price) for row in (*self.selections, *self.table_cxhh))
		if not self.sign_up_fund and priced and not is_freely_given(self.discounts):
			frappe.throw(_("Choose a Sign-Up Fund on the Registration tab to take the sign-up payments."))
		# Only when they change: an attendance save of the Function must not trip it.
		if any(self.has_value_changed(field) for field in ("sign_up_fund", "church", "is_shared")):
			refuse_another_churches_fund(self, self.sign_up_fund)

	def promote_waitlist_when_capacity_grows(self):
		"""A raised capacity, or a selection's, gives the new seats to the waitlist."""

		def get_limits(doc):
			selections = sorted((row.selection, cint(row.capacity)) for row in doc.selections)
			items = sorted(
				(row.item, cint(row.quantity_needed), cint(row.is_limited)) for row in doc.table_cxhh
			)
			return cint(doc.capacity), selections, items

		before = self.get_doc_before_save()
		if before and get_limits(before) != get_limits(self):
			# After the commit: the promoted sign-ups save this Function's attendance, which would leave
			# the copy the form gets back stale.
			frappe.enqueue(
				"churchit.church_ministries.doctype.function_sign_up.function_sign_up.promote_waitlist",
				function=self.name,
				enqueue_after_commit=True,
			)

	def settle_payment_holds_when_prices_change(self):
		"""A lower price or a new discount, such as Offer It Freely, reaches the sign-ups that wait to pay."""

		def get_prices(doc):
			selections = sorted((row.selection, flt(row.price)) for row in doc.selections)
			items = sorted((row.item, flt(row.price)) for row in doc.table_cxhh)
			discounts = sorted(
				(row.kind, row.code or "", flt(row.amount), flt(row.percent), str(row.valid_until or ""))
				for row in doc.discounts
			)
			return selections, items, discounts

		before = self.get_doc_before_save()
		if before and get_prices(before) != get_prices(self):
			frappe.enqueue(
				"churchit.church_ministries.doctype.function_sign_up.function_sign_up.settle_payment_holds",
				function=self.name,
				enqueue_after_commit=True,
			)

	def validate_group(self):
		"""A group belongs to one church, so its meetings do too."""
		if self.group and self.is_shared:
			frappe.throw(_("A Function with a Group cannot be shared with all churches."))
		refuse_another_churches_record(self, "Group", self.group)

	def refuse_new_group_associations(self):
		"""A Function names its group in Group. Rows kept from before that field stay as they are."""
		if self.is_new() and self.source_template:
			return  # An occurrence keeps the rows its template has.
		before = self.get_doc_before_save()
		rows_before = before.associations if before else []
		kept = {row.association for row in rows_before if row.association_type == "Group"}
		for row in self.associations:
			if row.association_type == "Group" and row.association not in kept:
				frappe.throw(_("Choose the group in the Group field, not in Associations."))

	def before_save(self):
		name = self.function_name or ""
		if self.start_date:
			self.title = f"{name}: {self.start_date}"
		else:
			self.title = name

		self.attendance_total = get_attendance_total(self.attendance or [], self.start_date, self.headcount)

	def on_trash(self):
		"""Keep a deleted occurrence deleted: its template skips the date from now on."""
		if not self.source_template:
			return
		# Its copied bookings go with it, or they would block the delete.
		# church-scope: only the bookings of this occurrence
		for booking in frappe.get_all("Room Booking", filters={"function": self.name}, pluck="name"):
			frappe.delete_doc("Room Booking", booking, ignore_permissions=True)
		if not frappe.db.exists("Function", self.source_template):
			return
		# Locked, so a second delete waits for the first one's skip date instead of a timestamp clash.
		template = frappe.get_doc("Function", self.source_template, for_update=True)
		if template.church != self.church:
			return
		if getdate(self.start_date) in {getdate(row.date) for row in template.skip_dates}:
			return
		template.append("skip_dates", {"date": self.start_date, "reason": _("Occurrence deleted")})
		template.save(ignore_permissions=True)


@frappe.whitelist()
def apply_template(source_name: str, start_date: str | None = None):
	"""The shape of a template function, to start a new one from on `start_date`.

	Templates are shared configuration: a branch may apply the main church's, so
	the source is not measured against the reader's church. It does have to be a
	template, though, or naming any function would hand over its plan and the
	people in it.
	"""
	frappe.has_permission("Function", "read", throw=True)
	refuse_a_source_that_is_not_a_template(source_name)
	template_dict = frappe.get_doc("Function", source_name).as_dict()

	copied_doc = {}

	# Specify which fields to include (whitelist approach)
	include_fields = [
		"address",
		"meeting_url",
		"all_day",
		"description",
		"associated_ministry",
		"group",
		"min_age",
		"max_age",
		"min_grade",
		"max_grade",
	]

	# Copy normal fields
	for field in include_fields:
		if field in template_dict:
			copied_doc[field] = template_dict[field]

	# Copy child tables
	include_child_tables = ["associations", "attendance", "schedule", "team_needs"]
	for child_table in include_child_tables:
		if template_dict.get(child_table):
			copied_doc[child_table] = [dict(child_row) for child_row in template_dict[child_table]]
	copied_doc["attendance"] = readable_attendance(copied_doc.get("attendance"))

	if start_date:
		move_schedule(copied_doc.get("schedule", []), date_diff(start_date, template_dict.start_date))
	return copied_doc


def move_schedule(rows: list[dict], days: int) -> None:
	"""Move each schedule row's start and end by `days`, so the schedule keeps to its function's date."""
	for row in rows:
		for field in ("start", "end"):
			if row.get(field):
				row[field] = add_days(get_datetime(row[field]), days)


def get_time_window(function) -> tuple[datetime, datetime]:
	"""When *function* starts and ends. An all-day function, or a missing time, takes the whole day."""
	start_date = getdate(function.start_date)
	end_date = getdate(function.end_date or function.start_date)
	if function.all_day or not function.start_time:
		return datetime.combine(start_date, time.min), datetime.combine(end_date, time.max)

	end_time = _as_time(function.end_time) if function.end_time else time.max
	return datetime.combine(start_date, _as_time(function.start_time)), datetime.combine(end_date, end_time)


def get_schedule_rows(function) -> list[frappe._dict]:
	"""*function*'s schedule as (time, title, detail, is_header) rows: a linked item's title, else the description."""
	rows = []
	for item in function.schedule:
		title = link_title(item.item_type, item.item) if item.item else None
		rows.append(
			frappe._dict(
				time=format_datetime(item.start, TIME_FORMAT) if item.start else None,
				title=title or item.description,
				detail=(item.description or item.item_type) if title else None,
				is_header=cint(item.is_header),
			)
		)
	return rows


def get_team_schedule(function, person: str) -> frappe._dict:
	"""*function*'s schedule as the Ministry Team page shows it to *person*, who serves at it.

	The song keys and arrangements, team notes, need notes and song media come only with the
	positions *person* has not declined. They are read here by doctype name, so the published-field
	scan finds them.
	"""
	# Imported here: both modules import this one.
	from churchit.church_ministries.doctype.ministry_team_assignment.ministry_team_assignment import DECLINED
	from churchit.church_ministries.songs.media import get_media_link

	rows = get_schedule_rows(function)
	# church-scope: the person's own assignments at a function they serve at
	assignments = frappe.get_all(
		"Ministry Team Assignment",
		filters={"function": function.name, "person": person, "status": ("!=", DECLINED)},
		fields=["name", "position"],
		order_by="creation asc",
	)
	if not assignments:
		return frappe._dict(rows=rows, need_notes=[])

	need_notes = frappe.get_all(
		"Function Team Need",
		filters={
			"parenttype": "Function",
			"parent": function.name,
			"position": ("in", [row.position for row in assignments]),
			"notes": ("is", "set"),
		},
		fields=["position", "notes"],
		order_by="idx asc",
	)
	for note in need_notes:
		note.position = link_title("Ministry Team Position", note.position)

	team_details = {
		item.name: item
		for item in frappe.get_all(
			"Function Schedule",
			filters={"parenttype": "Function", "parent": function.name},
			fields=["name", "item_type", "item", "song_key", "arrangement", "notes"],
		)
	}
	songs = {item.item for item in team_details.values() if item.item_type == "Song" and item.item}
	media = (
		frappe.get_all(
			"Song Media",
			filters={"parenttype": "Song", "parent": ("in", list(songs))},
			fields=["name", "parent", "media_type", "label", "file", "url"],
			order_by="idx asc",
		)
		if songs
		else []
	)
	for row, item in zip(rows, function.schedule, strict=True):
		details = team_details[item.name]
		is_song = details.item_type == "Song"
		row.update(
			key=details.song_key if is_song else None,
			arrangement=details.arrangement if is_song else None,
			notes=details.notes,
			media=[
				get_media_link(assignments[0].name, file)
				for file in media
				if is_song and file.parent == details.item and (file.file or file.url)
			],
		)
	return frappe._dict(rows=rows, need_notes=need_notes)


def refuse_a_source_that_is_not_a_template(source_name):
	"""Allow a function the reader may see, or one a Function Type names as its template."""
	if frappe.has_permission("Function", doc=source_name):
		return
	if frappe.db.exists("Function Type", {"template_function": source_name}):
		return
	frappe.throw(_("{0} is not a function template.").format(source_name), frappe.PermissionError)


def readable_attendance(rows):
	"""The attendance rows whose person the reader may see.

	A template carries the regulars of the function it came from, which is the
	point of copying them onto the next one. A template shared by another church
	carries that church's people, who are none of this reader's business.
	"""
	if not rows:
		return []
	people = [row.get("person") for row in rows if row.get("person")]
	if not people:
		return rows
	readable = set(frappe.get_list("Person", filters={"name": ("in", people)}, pluck="name"))
	return [row for row in rows if row.get("person") in readable]


def _as_time(value):
	if hasattr(value, "hour"):
		return value
	# timedelta from DB
	if isinstance(value, timedelta):
		total = int(value.total_seconds())
		return (datetime.min + timedelta(seconds=total)).time()
	# string fallback
	return datetime.strptime(str(value), "%H:%M:%S").time()

# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""What the automatic sections of a Bulletin print, read from the rest of the app."""

import frappe
from frappe.utils import add_days, format_datetime, format_time, formatdate, getdate

from churchit.church_foundations.doctype.church.church import ADDRESS_FIELDS, address_line, get_church
from churchit.church_people import celebrations
from churchit.church_scope import church_filters

TIME_FORMAT = "h:mm a"


class BulletinSections:
	"""Content of the automatic sections of a Bulletin, for its print format.

	Mixed into the Bulletin document, so each property reads the bulletin's
	function and date and the shared Bulletin Settings.
	"""

	@property
	def settings(self):
		"""Bulletin Settings as this bulletin's church has them."""
		return frappe.get_cached_doc("Bulletin Settings").for_church(self.church)

	@property
	def church_doc(self):
		"""The Church this bulletin is for, falling back to the site's church."""
		return frappe.get_cached_doc("Church", self.church) if self.church else get_church()

	@property
	def contact_information(self):
		"""The church's name, address, phone, email and website."""
		church = self.church_doc
		contact = frappe.get_cached_doc("Contact Us Settings")
		address = None
		if church and church.address:
			address = frappe.db.get_value("Address", church.address, ADDRESS_FIELDS, as_dict=True)
		return frappe._dict(
			name=church.church_name if church else None,
			address=address_line(address),
			phone=contact.phone,
			email=contact.email_id,
			website=frappe.utils.get_url().split("://", 1)[-1],
		)

	@property
	def order_of_worship(self):
		"""The function's schedule as (time, title, detail) rows."""
		rows = []
		for item in self.function_doc.schedule:
			title = link_title(item.item_type, item.item) if item.item else None
			rows.append(
				frappe._dict(
					time=format_datetime(item.start, TIME_FORMAT) if item.start else None,
					title=title or item.description,
					detail=(item.description or item.item_type) if title else None,
				)
			)
		return rows

	@property
	def church_roles(self):
		"""The configured positions with the people holding them on the function date."""
		roles = []
		for row in self.settings.roles:
			people = position_holders(row.position_type, self.function_date, self.church)
			if people:
				roles.append(frappe._dict(role=row.position_type, people=people))
		return roles

	@property
	def upcoming_functions(self):
		"""Functions in the days after this one, as (day, time, name) rows."""
		start = add_days(self.function_date, 1)
		end = add_days(self.function_date, self.settings.upcoming_functions_days)
		functions = frappe.get_all(
			"Function",
			filters=church_filters(
				self.church, start_date=("between", [start, end]), name=("!=", self.function)
			),
			fields=["function_name", "start_date", "start_time", "all_day"],
			order_by="start_date asc, start_time asc",
		)
		return [
			frappe._dict(
				day=formatdate(function.start_date, "EEE, MMM d"),
				time=None
				if function.all_day or not function.start_time
				else format_time(function.start_time, TIME_FORMAT),
				name=function.function_name,
			)
			for function in functions
		]

	@property
	def ministries(self):
		return frappe.get_all(
			"Ministry",
			filters=church_filters(self.church, status="Active"),
			fields=["ministry_name", "mission_statement"],
			order_by="ministry_name asc",
		)

	@property
	def featured_missionary(self):
		"""The chosen missionary's title, photo, country and agency line, and mission statement."""
		if not self.missionary:
			return None
		missionary = frappe.get_cached_doc("Missionary", self.missionary)
		agency = link_title("Missionary Agency", missionary.agency) if missionary.agency else None
		return frappe._dict(
			title=missionary.title,
			photo=missionary.photo,
			where=" · ".join(filter(None, [missionary.country, agency])),
			mission_statement=missionary.mission_statement,
		)

	@property
	def verse_of_the_week(self):
		return frappe.get_cached_doc("Bible Reference", self.verse) if self.verse else None

	@property
	def church_verse(self):
		"""The Church record's key verse, printed on the back cover."""
		church = self.church_doc
		if not church or not church.church_verse:
			return None
		return frappe.get_cached_doc("Bible Reference", church.church_verse)

	@property
	def church_image(self):
		"""The Church record's logo or photo, printed on the front cover."""
		church = self.church_doc
		return church.image if church else None

	@property
	def birthdays(self):
		members_only = self.settings.birthday_scope == "Active Members"
		return celebrations.birthdays(*self.celebration_window, members_only=members_only, church=self.church)

	@property
	def anniversaries(self):
		members_only = self.settings.anniversary_scope == "Active Members"
		return celebrations.anniversaries(
			*self.celebration_window, members_only=members_only, church=self.church
		)

	@property
	def celebration_window(self):
		"""First and last day covered by the birthdays and anniversaries sections."""
		start = getdate(self.function_date)
		return start, add_days(start, max(self.settings.celebration_days, 1) - 1)

	@property
	def sermon_handouts(self):
		"""Handouts of the sermons on the function's schedule, each with its sermon."""
		handouts = []
		for item in self.function_doc.schedule:
			if item.item_type != "Sermon" or not item.item:
				continue
			sermon = frappe.get_doc("Sermon", item.item)
			if sermon.handout:
				handouts.append(
					frappe._dict(
						sermon=sermon,
						handout=frappe.get_doc("Sermon Handout", sermon.handout),
						preacher=link_title("Person", sermon.prepared_by) if sermon.prepared_by else None,
					)
				)
		return handouts

	@property
	def function_doc(self):
		return frappe.get_doc("Function", self.function)


def position_holders(position_type, on_date, church=None):
	"""Full names of the people holding *position_type* on *on_date*, alphabetically."""
	# church-scope: scoped by the church the bulletin passes in
	Position = frappe.qb.DocType("Position")
	Person = frappe.qb.DocType("Person")
	query = (
		frappe.qb.from_(Position)
		.join(Person)
		.on(Position.parent == Person.name)
		.select(Person.full_name)
		.where((Position.parenttype == "Person") & (Position.position == position_type))
		.where(Position.start_date.isnull() | (Position.start_date <= on_date))
		.where(Position.end_date.isnull() | (Position.end_date >= on_date))
		.orderby(Person.full_name)
	)
	if church:
		query = query.where(Person.church == church)
	return query.run(pluck=True)


def link_title(doctype, name):
	"""The record's title, or its name for doctypes without a title field."""
	title_field = frappe.get_meta(doctype).title_field
	return (frappe.db.get_value(doctype, name, title_field) if title_field else None) or name

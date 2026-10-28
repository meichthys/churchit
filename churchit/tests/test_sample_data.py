# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The sample data loader behind the setup wizard opt-in and the Settings workspace link.

The loader inserts through the normal document API across nearly every module, so
these double as an integration check: a validation added anywhere that the sample
records violate surfaces here rather than on a new user's first install.
"""

from collections import deque
from unittest.mock import patch

import frappe
from frappe.desk.doctype.dashboard_chart import dashboard_chart
from frappe.desk.doctype.number_card.number_card import calculate_previous_result
from frappe.email.doctype.email_queue.email_queue import EmailQueue
from frappe.tests.utils import FrappeTestCase
from frappe.utils import background_jobs, get_first_day_of_week, today

from churchit.church_finances.doctype.giving_statement.giving_statement import generate_statements
from churchit.church_people import household
from churchit.church_people.dashboard_chart_source.life_events import life_events
from churchit.church_people.report.person_anniversaries_this_month import (
	person_anniversaries_this_month as anniversaries_this_month,
)
from churchit.church_people.report.person_positions_ending_this_month import (
	person_positions_ending_this_month as positions_ending_this_month,
)
from churchit.dashboard import count_people
from churchit.setup import sample_data
from churchit.tests.helpers import ensure_root_church, make_person

# One or two doctypes per module, enough to prove each section of the loader ran.
SEEDED_DOCTYPES = (
	"Person",
	"Family",
	"Missionary",
	"Missionary Agency",
	"Fund",
	"Expense",
	"Collection",
	"Budget",
	"Function",
	"Group",
	"Ministry",
	"Prayer Request",
	"Prayer",
	"Bible Memory Item",
	"Sermon",
	"Belief",
	"Location",
	"Room",
	"Church Asset",
	"Church Task",
	"Song",
	"Meeting Minutes",
	"Weekly Metrics",
	"Pledge Campaign",
	"Pledge",
	"Question Set",
	"Form Response",
	"Function Sign-Up",
	"Group Join Request",
	"Pickup Restriction",
	"Background Check",
	"Sermon Handout",
	"Bulletin",
)


def counts():
	return {doctype: frappe.db.count(doctype) for doctype in SEEDED_DOCTYPES}


def get_database_state() -> dict:
	"""Every table's row count, the Series counters, the Singles values and the default Church."""
	church = frappe.db.get_value("Church", ensure_root_church(), "*", as_dict=True)
	return {
		"rows": {
			table: frappe.db.sql(f"select count(*) from `{table}`")[0][0]
			for table in frappe.db.get_tables(cached=False)
		},
		"series": dict(frappe.db.sql("select name, current from tabSeries")),
		"singles": {
			(doctype, field): value
			for doctype, field, value in frappe.db.sql("select doctype, field, value from tabSingles")
			if field not in ("modified", "modified_by")
		},
		"church": {key: value for key, value in church.items() if key not in ("modified", "modified_by")},
	}


def get_changes(before: dict, after: dict) -> dict:
	return {
		key: (before.get(key), after.get(key))
		for key in before.keys() | after.keys()
		if before.get(key) != after.get(key)
	}


def add_outgoing_email_account():
	frappe.get_doc(
		{
			"doctype": "Email Account",
			"email_account_name": "_Test Sample Data Outgoing",
			"email_id": "_test_sample_outgoing@example.com",
			"enable_outgoing": 1,
			"default_outgoing": 1,
			"smtp_server": "localhost",
			"no_smtp_authentication": 1,
		}
	).insert(ignore_permissions=True)


class QueuedJobs:
	"""Holds what `frappe.enqueue` queues, to run it the way a worker does after a commit.

	In a test, enqueue pushes a job to the real queue at once, where a worker runs it
	against the committed database, and a job queued after commit never runs at all.
	"""

	enqueue_now = staticmethod(background_jobs.enqueue)

	def __init__(self):
		self.jobs = deque()

	def enqueue(self, method, **kwargs):
		if kwargs.get("now"):
			return self.enqueue_now(method, **kwargs)
		self.jobs.append((method, kwargs))

	def run(self):
		"""Stand in for a commit: its callbacks, then every queued job, and the jobs those queue."""
		frappe.db.after_commit.run()
		while self.jobs:
			method, kwargs = self.jobs.popleft()
			self.enqueue_now(method, **{**kwargs, "now": True})


class TestSampleDataLoader(FrappeTestCase):
	"""Loaded once for the class: the test transaction spans every method here."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		sample_data.create_sample_data()

	def test_seeds_every_module(self):
		empty = [doctype for doctype in SEEDED_DOCTYPES if not frappe.db.count(doctype)]
		self.assertEqual(empty, [], "loader produced no records for these doctypes")

	def test_running_twice_adds_nothing(self):
		"""The module docstring promises a second run is safe."""
		before = counts()
		sample_data.create_sample_data()
		self.assertEqual(counts(), before)

	def test_demo_passwords_are_the_email_on_every_run(self):
		from frappe.utils.password import check_password

		frappe.utils.password.update_password(sample_data._CHURCH_MANAGER_EMAIL, "something-else")
		sample_data.create_sample_data()
		self.assertEqual(
			check_password(sample_data._CHURCH_MANAGER_EMAIL, sample_data._CHURCH_MANAGER_EMAIL),
			sample_data._CHURCH_MANAGER_EMAIL,
		)

	def test_demo_logins_are_linked_to_their_person(self):
		for email, person, _role_profile in sample_data._SAMPLE_USERS:
			self.assertTrue(frappe.db.exists("User", email), f"{email} was not created")
			linked = frappe.db.get_value("Person", {"user": email}, "full_name")
			self.assertEqual(linked, person, f"{email} is linked to the wrong Person")

	def test_demo_logins_cover_both_staff_and_a_plain_member(self):
		"""A member account is the only way to see the portal, since staff are
		System Users and Frappe hides its /me Portal link from them."""
		types = {
			email: frappe.db.get_value("User", email, "user_type")
			for email, _person, _profile in sample_data._SAMPLE_USERS
		}
		self.assertEqual(types.pop(sample_data._CHURCH_MEMBER_EMAIL), "Website User")
		self.assertEqual(set(types.values()), {"System User"})

	def test_the_member_has_giving_to_show_on_a_statement(self):
		person = frappe.db.get_value("Person", {"user": sample_data._CHURCH_MEMBER_EMAIL}, "name")
		self.assertTrue(
			frappe.db.exists("Donation", {"person": person, "parenttype": "Collection"}),
			"the demo member needs gifts, or their statement renders empty",
		)

	def test_the_monthly_people_reports_always_have_a_row(self):
		"""Fixed dates left these empty for eleven months of the year."""
		for report in (anniversaries_this_month, positions_ending_this_month):
			_columns, rows = report.execute({})
			self.assertTrue(rows, f"{report.__name__} is empty after loading sample data")

	def test_a_group_is_public_so_the_portal_has_something_to_join(self):
		self.assertTrue(frappe.db.exists("Group", {"public": 1, "show_in_portal": 1}))

	def test_the_manager_and_the_loader_have_assignments(self):
		for user in (sample_data._CHURCH_MANAGER_EMAIL, frappe.session.user):
			self.assertTrue(frappe.db.exists("ToDo", {"allocated_to": user, "status": "Open"}), user)

	def test_the_yearly_cards_have_a_year_to_compare_with(self):
		"""Frappe shows a card's change only when records existed a year ago."""
		for card in ("Ministries", "Total Missionaries"):
			doc = frappe.get_doc("Number Card", card)
			self.assertTrue(calculate_previous_result(doc, doc.filters_json), card)

	def test_collections_are_submitted_so_funds_carry_a_balance(self):
		self.assertTrue(frappe.db.exists("Collection", {"docstatus": 1}))
		self.assertTrue(any(frappe.get_all("Fund", pluck="balance")))

	def test_both_members_cards_count_the_same_people(self):
		"""The Summary card counted every active person, Regular Attenders too."""
		people_card, summary_card = (
			count_people(frappe.db.get_value("Number Card", card, "filters_json"))["value"]
			for card in ("Members", "Total Members")
		)
		self.assertTrue(people_card)
		self.assertEqual(summary_card, people_card)


class TestSampleDataRoundTrip(FrappeTestCase):
	"""A wipe, one load and one wipe for the whole class, then what the wipe had to leave behind.

	Its own class so the wipe does not strand the loader tests above.
	delete_sample_data() runs on unfiltered doctypes, so it clears every record of
	them on whatever site the suite runs against, not only the seeded ones. The
	first wipe makes the load start from nothing, as on a new site, even when the
	site already has sample data.

	The round trip is in setUpClass because a load and a wipe cost seconds each:
	one cycle, with what each test needs recorded on the way past, buys the same
	coverage as a cycle per test.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.jobs = QueuedJobs()
		for target in ("frappe.enqueue", "frappe.utils.background_jobs.enqueue"):
			enqueue = patch(target, cls.jobs.enqueue)
			enqueue.start()
			cls.addClassCleanup(enqueue.stop)
		# With an outgoing account the load queues registrant emails; none is sent.
		send = patch.object(EmailQueue, "send")
		send.start()
		cls.addClassCleanup(send.stop)
		add_outgoing_email_account()

		sample_data.delete_sample_data()
		cls.jobs.run()
		cls.before = get_database_state()
		# A church's own record from before the load, which the delete takes with the rest of its doctype.
		cls.own_person = make_person("_Test Own Person").name

		sample_data.create_sample_data()
		cls.jobs.run()
		cls.queued_emails = frappe.db.count("Email Queue") - cls.before["rows"]["tabEmail Queue"]
		cls.check_in_cards = frappe.db.count("Follow-up Card", {"source_type": "Function Check-In"})
		sample_families = frappe.get_all(
			"Family",
			{"family_name": ["in", [name for name, _members in sample_data._FAMILIES]]},
			pluck="name",
		)
		cls.spouse_roles = frappe.get_all(
			"Family Members",
			filters={
				"parenttype": "Family",
				"parent": ["in", sample_families],
				"relationship_to_primary_contact": ["in", ["Husband", "Wife"]],
			},
			pluck="household_role",
		)
		cls.charts_with_data = cls.get_charts_with_data()
		cls.this_week = frappe.get_all(
			"Weekly Metrics",
			{"week_start": get_first_day_of_week(today())},
			["people_in_groups"],
		)
		cls.people_in_groups = frappe.db.count("Person", {"group_count": [">", 0]})
		cls.johnson_salutation = household.salutation(
			frappe.db.get_value("Family", {"family_name": "Johnson - Robert"})
		)
		cls.home_addresses = frappe.get_all(
			"Address", {"address_title": ["in", list(sample_data._HOME_ADDRESSES)]}, pluck="name"
		)
		cls.linked_home_addresses = frappe.db.count("Postal Address", {"address": ["in", cls.home_addresses]})
		generate_statements("2000-01-01", "2100-12-31")
		cls.statements = frappe.db.count("Giving Statement")
		cls.draft_expense = bool(frappe.db.exists("Expense", {"docstatus": 0}))
		cls.submitted_expense = bool(frappe.db.exists("Expense", {"docstatus": 1}))
		cls.function_type = cls.add_records_a_user_would_make()
		# The first wipe took every record of these, so assignments on them are the sample's.
		cls.assignments = frappe.get_all(
			"ToDo",
			filters={
				"reference_type": [
					"in",
					["Person", "Alms Request", "Prayer Request", "Church Task", "Function"],
				]
			},
			pluck="name",
		)

		sample_data.delete_sample_data()
		cls.jobs.run()
		cls.after = get_database_state()

	@classmethod
	def get_charts_with_data(cls) -> list[str]:
		charts = []
		for name in ("Members", "Baptisms by Year"):
			chart = frappe.get_doc("Dashboard Chart", name)
			data = life_events.get(
				filters=chart.filters_json, timespan=chart.timespan, time_interval=chart.time_interval
			)
			if any(data["datasets"][0]["values"]):
				charts.append(name)
		for name in ("Attendance by Week", "Giving by Week"):
			if any(dashboard_chart.get(chart_name=name, refresh=1)["datasets"][0]["values"]):
				charts.append(name)
		return charts

	@classmethod
	def add_records_a_user_would_make(cls):
		"""Records nothing seeds but that link to sample records, so the wipe has to take them too."""
		person = frappe.get_all("Person", limit=1, pluck="name")[0]
		fund = frappe.get_all("Fund", limit=1, pluck="name")[0]
		function = frappe.get_all("Function", limit=1, pluck="name")[0]
		check_type = frappe.get_all("Background Check Type", limit=1, pluck="name")[0]
		frappe.get_doc({"doctype": "Bulletin", "function": function}).insert()
		frappe.get_doc({"doctype": "Online Donation", "person": person, "fund": fund, "amount": 5}).insert()
		frappe.get_doc(
			{
				"doctype": "Background Check",
				"person": person,
				"check_type": check_type,
				"status": "Requested",
				"requested_on": frappe.utils.today(),
			}
		).insert()

		function_type = frappe.get_all("Function Type", limit=1, pluck="name")[0]
		frappe.db.set_value("Function Type", function_type, "template_function", function)
		return function_type

	def test_both_spouses_of_a_sample_household_are_adults(self):
		"""Setting the primary contact before the spouse link made each wife an Other Adult."""
		self.assertEqual(len(self.spouse_roles), 2 * len(sample_data._SPOUSES))
		self.assertEqual(set(self.spouse_roles), {household.ADULT})
		self.assertEqual(self.johnson_salutation, "Robert & Mary Johnson")

	def test_the_people_and_summary_charts_have_data(self):
		"""Membership and baptism dates in 2015 and no Weekly Metrics left these charts empty."""
		self.assertEqual(
			self.charts_with_data, ["Members", "Baptisms by Year", "Attendance by Week", "Giving by Week"]
		)

	def test_this_weeks_metrics_count_the_people_in_groups(self):
		"""The week was written before the queued summary refresh filled the group counts it reads."""
		self.assertGreater(self.people_in_groups, 0)
		self.assertEqual(sum(row.people_in_groups for row in self.this_week), self.people_in_groups)

	def test_delete_leaves_every_table_as_it_was(self):
		"""Rows the load made through Frappe (versions, comments, milestones, logs) go with the records."""
		for part in ("rows", "series", "singles", "church"):
			with self.subTest(part):
				self.assertEqual(get_changes(self.before[part], self.after[part]), {})

	def test_the_round_trip_covers_queued_emails(self):
		self.assertTrue(self.queued_emails, "the load queued no email, so the delete was not tested on any")

	def test_the_sample_check_ins_start_no_newcomer_card(self):
		"""The people checked in are long-time members, not newcomers."""
		self.assertEqual(self.check_in_cards, 0)

	def test_an_emptied_doctype_numbers_its_next_record_from_one(self):
		self.assertTrue(self.own_person.endswith("-0001"), self.own_person)
		frappe.db.savepoint("next_person")
		next_person = make_person("_Test After Delete").name
		frappe.db.rollback(save_point="next_person")
		self.assertEqual(next_person, self.own_person)

	def test_delete_removes_what_create_made(self):
		# Ministry is the one step with a filter: the General ministry predates the
		# sample data and is meant to survive.
		remaining = [
			doctype for doctype in SEEDED_DOCTYPES if doctype != "Ministry" and frappe.db.count(doctype)
		]
		self.assertEqual(remaining, [])
		self.assertFalse(frappe.db.exists("User", sample_data._CHURCH_MANAGER_EMAIL))

	def test_families_and_people_without_one_get_a_home_address_that_delete_removes(self):
		self.assertEqual(len(self.home_addresses), len(sample_data._HOME_ADDRESSES))
		self.assertEqual(self.linked_home_addresses, len(sample_data._HOME_ADDRESSES))
		self.assertFalse(frappe.db.exists("Address", {"name": ["in", self.home_addresses]}))

	def test_delete_leaves_the_church_saveable(self):
		"""The Church survives the wipe; a link left pointing into it would strand the record."""
		frappe.get_doc("Church", ensure_root_church()).save(ignore_permissions=True)

	def test_delete_removes_statements_issued_from_sample_giving(self):
		"""Statements are generated, not seeded, but link to sample people, families
		and funds; leaving them behind strands those links as raw IDs."""
		self.assertTrue(self.statements, "the sample giving issued no statements to wipe")
		self.assertEqual(frappe.db.count("Giving Statement"), 0)

	def test_delete_removes_records_that_users_make_from_sample_data(self):
		"""Not seeded, but they link to sample records and would otherwise dangle."""
		for doctype in ("Bulletin", "Online Donation", "Background Check"):
			self.assertEqual(frappe.db.count(doctype), 0, doctype)
		self.assertFalse(frappe.db.get_value("Function Type", self.function_type, "template_function"))

	def test_delete_removes_the_assignments(self):
		self.assertTrue(self.assignments, "the sample data assigned nothing to wipe")
		self.assertFalse(frappe.db.exists("ToDo", {"name": ["in", self.assignments]}))

	def test_delete_removes_draft_and_submitted_expenses_alike(self):
		self.assertTrue(self.draft_expense, "the sample data seeded no draft expense to wipe")
		self.assertTrue(self.submitted_expense, "the sample data seeded no submitted expense to wipe")
		self.assertEqual(frappe.db.count("Expense"), 0)


class TestSetupWizardHook(FrappeTestCase):
	"""The opt-in gate, checked without paying for a full load."""

	def test_creates_when_opted_in(self):
		with patch.object(sample_data, "create_sample_data") as create:
			sample_data.setup_wizard_complete({"create_sample_data": 1})
		create.assert_called_once()

	def test_skips_when_not_opted_in(self):
		with patch.object(sample_data, "create_sample_data") as create:
			sample_data.setup_wizard_complete({})
			sample_data.setup_wizard_complete({"create_sample_data": 0})
			sample_data.setup_wizard_complete(None)
		create.assert_not_called()

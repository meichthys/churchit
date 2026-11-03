# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""Every module's onboarding must be reachable, complete, and its tours must point at real fields.

Each failure here is silent: an onboarding that no workspace block names is never rendered, a step
without a form tour drops the user on an unexplained form, and a tour step naming a field that was
since renamed or hidden stalls the tour with no error.

Onboarding Step carries no module field, so the app's own steps are enumerated from the folders
they ship in rather than filtered out of the table.
"""

import json
import os

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.tests.test_desk_ui_hygiene import assert_list_ratchet, get_enclosing_breaks

# The Church onboarding belongs on Summary, the page a new church lands on, so Settings and Help
# offer none of their own.
MODULES_WITHOUT_ONBOARDING = {"Church Setup", "Church Help"}

# frappe's onboarding widget runs a tour from these two actions only (create_entry and
# show_form_tour in public/js/frappe/widgets/onboarding_widget.js). "Go to Page" and
# "Update Settings" route to the form and ignore the step's form_tour entirely.
ACTIONS_THAT_RUN_A_TOUR = ("Create Entry", "Show Form Tour")

# Module Onboardings that no workspace of their module shows yet, with the reason.
ONBOARDINGS_NOT_ON_A_WORKSPACE = {}

# Tours whose steps run against the order of the form, with the phase of the UX roadmap that fixes them,
# or the reason the work goes in another order. U13 puts 'Take the Tour' on every form with a tour, so it reorders the tours of forms no other phase changes.
TOURS_OUT_OF_ORDER = {
	"Family": "The Primary Contact is chosen from the members, so the tour asks for the members first",
	"Budget": "U8",
	"Expense": "U8",
	"Fund": "U8",
	"Bulletin": "U10",
	"Missionary": "U10",
	"Missionary Agency": "U10",
	"Prayer Request": "U10",
	"Sermon": "U10",
	"Church Asset": "U11",
	"Church Task": "U11",
	"About Us Settings": "U13",
	"Contact Us Settings": "U13",
	"Email Account Setup": "U13",
	"Website Settings": "U13",
}


class TestOnboardingHygiene(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.modules = frappe.get_module_list("churchit")
		cls.onboardings = frappe.get_all(
			"Module Onboarding", filters={"module": ["in", cls.modules]}, pluck="name"
		)

	def test_every_module_with_a_workspace_has_an_onboarding(self):
		"""A church module the user can open should tell them what to set up in it."""
		missing = sorted(
			set(self.user_facing_modules()) - set(self.onboarding_modules()) - MODULES_WITHOUT_ONBOARDING
		)
		self.assertEqual(missing, [], f"Church modules without a Module Onboarding: {missing}")

	def test_every_onboarding_is_shown_on_a_workspace_of_its_module(self):
		"""The desk renders an onboarding only from an `onboarding` block in a workspace's content.

		frappe.desk.desktop.Workspace reads those blocks; Frappe 16.50 removed the sidebar panel.
		"""
		shown = {
			(workspace.module, block["data"]["onboarding_name"])
			for workspace in frappe.get_all(
				"Workspace",
				filters={"module": ["in", self.modules], "standard": 1},
				fields=["module", "content"],
			)
			for block in json.loads(workspace.content or "[]")
			if block["type"] == "onboarding"
		}
		not_shown = sorted(
			onboarding.name
			for onboarding in frappe.get_all(
				"Module Onboarding", filters={"name": ["in", self.onboardings]}, fields=["name", "module"]
			)
			if (onboarding.module, onboarding.name) not in shown
		)
		self.assertEqual(
			not_shown,
			sorted(ONBOARDINGS_NOT_ON_A_WORKSPACE),
			"Add an onboarding block to a workspace of the onboarding's module, "
			"or drop a fixed onboarding from ONBOARDINGS_NOT_ON_A_WORKSPACE",
		)

	def test_every_step_belongs_to_an_onboarding(self):
		orphans = sorted(set(self.shipped_steps()) - set(self.listed_steps()))
		self.assertEqual(orphans, [], f"Onboarding Steps no onboarding lists: {orphans}")

	def test_every_step_with_a_form_has_a_form_tour(self):
		"""A step that opens a form must explain it; one that only opens a page need not."""
		missing = [
			step.name
			for step in self.steps()
			if step.reference_document and not (step.form_tour and step.show_form_tour)
		]
		self.assertEqual(missing, [], f"Onboarding Steps without a form tour: {missing}")

	def test_every_step_with_a_tour_uses_an_action_that_runs_it(self):
		"""A tour on any other action is dead configuration: the widget never starts it."""
		ignored = [
			(step.name, step.action)
			for step in self.steps()
			if step.form_tour and step.action not in ACTIONS_THAT_RUN_A_TOUR
		]
		self.assertEqual(ignored, [], f"Onboarding Steps whose form tour never runs: {ignored}")

	def test_create_entry_steps_open_the_full_form(self):
		"""Without Show Full Form the widget opens quick entry, which runs no tour."""
		quick_entry = [
			step.name
			for step in self.steps()
			if step.action == "Create Entry" and step.form_tour and not step.show_full_form
		]
		self.assertEqual(quick_entry, [], f"Onboarding Steps that skip the full form: {quick_entry}")

	def test_every_form_tour_explains_the_step_it_is_attached_to(self):
		mismatched = [
			(step.name, step.form_tour)
			for step in self.steps()
			if step.form_tour
			and frappe.db.get_value("Form Tour", step.form_tour, "reference_doctype")
			!= step.reference_document
		]
		self.assertEqual(mismatched, [])

	def test_tour_steps_point_at_visible_fields(self):
		"""A tour stalls on a step whose field a single-church site does not draw."""
		broken = []
		for tour in frappe.get_all(
			"Form Tour", filters={"module": ["in", self.modules]}, fields=["name", "reference_doctype"]
		):
			if not tour.reference_doctype:
				continue
			meta = frappe.get_meta(tour.reference_doctype)
			for row in frappe.get_all("Form Tour Step", filters={"parent": tour.name}, pluck="fieldname"):
				field = meta.get_field(row)
				if not field:
					broken.append((tour.name, row, "no such field"))
					continue
				for reason in self.get_reasons_not_drawn(field, get_enclosing_breaks(meta, row)):
					broken.append((tour.name, row, reason))
		self.assertEqual(broken, [])

	@staticmethod
	def get_reasons_not_drawn(field, breaks):
		"""Why the form leaves out *field*: it, or a tab, section or column around it, is hidden or multi-church only."""
		switch = ("frappe.boot.churchit.multi_church", "frappe.boot.churchit.single_church")
		reasons = []
		for owner in (field, *breaks):
			if owner.hidden:
				reasons.append(f"{owner.fieldname} is hidden")
			if any(name in (owner.depends_on or "") for name in switch):
				reasons.append(f"{owner.fieldname} shows only with multi-church on")
		return reasons

	def steps(self):
		return frappe.get_all(
			"Onboarding Step",
			filters={"name": ["in", self.listed_steps()]},
			fields=[
				"name",
				"action",
				"reference_document",
				"form_tour",
				"show_form_tour",
				"show_full_form",
			],
		)

	def listed_steps(self):
		return frappe.get_all(
			"Onboarding Step Map", filters={"parent": ["in", self.onboardings]}, pluck="step"
		)

	def shipped_steps(self):
		"""The name in each step JSON the app ships, which the folder name cannot be unscrubbed to."""
		names = []
		for module in self.modules:
			folder = os.path.join(frappe.get_app_path("churchit"), frappe.scrub(module), "onboarding_step")
			for step in self.module_folders(module, "onboarding_step"):
				with open(os.path.join(folder, step, f"{step}.json")) as handle:
					names.append(json.load(handle)["name"])
		return names

	def onboarding_modules(self):
		return frappe.get_all("Module Onboarding", filters={"module": ["in", self.modules]}, pluck="module")

	def user_facing_modules(self):
		"""Church modules that own a workspace of their own, ignoring the manuals."""
		return [
			module
			for module in self.modules
			for workspace in self.module_folders(module, "workspace")
			if not workspace.startswith("manual")
		]

	@staticmethod
	def module_folders(module, doctype):
		path = os.path.join(frappe.get_app_path("churchit"), frappe.scrub(module), doctype)
		if not os.path.isdir(path):
			return []
		return sorted(entry for entry in os.listdir(path) if not entry.startswith("__"))

	def test_tour_steps_follow_the_order_of_the_form(self):
		"""A tour that jumps back up the form leaves the user hunting for the field it names next."""
		found = {}
		for tour in frappe.get_all(
			"Form Tour", filters={"module": ["in", self.modules]}, fields=["name", "reference_doctype"]
		):
			if not tour.reference_doctype:
				continue
			fieldnames = [field.fieldname for field in frappe.get_meta(tour.reference_doctype).fields]
			steps = frappe.get_all(
				"Form Tour Step", filters={"parent": tour.name}, pluck="fieldname", order_by="idx"
			)
			steps = [step for step in steps if step in fieldnames]
			if steps != sorted(steps, key=fieldnames.index):
				found[tour.name] = sorted(steps, key=fieldnames.index)
		assert_list_ratchet(self, found, TOURS_OUT_OF_ORDER, "Tour steps run against the form order")

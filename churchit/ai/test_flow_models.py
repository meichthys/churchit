# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""The privacy label on Flow Models: the field only a Frappe with Flow gets, who and when it was set,
and the lines of the exposure panel. Tests that need Flow skip on a Frappe without it (Frappe 16).
"""

from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import quote

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime

from churchit.ai.flow_models import (
	BY_FIELD,
	DEFAULT_LABEL,
	LABEL_FIELD,
	ON_FIELD,
	PRIVACY_LABEL_FIELDS,
	PRIVACY_LABELS,
	add_privacy_label_field,
	stamp_privacy_label,
)
from churchit.ai.switch import get_exposure, get_flow_model_lines, has_flow
from churchit.tests.helpers import RollbackEachTest, ensure_user

MANAGER = "_test_flow_models_system_manager@example.com"
OTHER_MANAGER = "_test_flow_models_other_manager@example.com"
CHURCH_MANAGER = "_test_flow_models_church_manager@example.com"


class TestLabelFieldOnlyWhereFlowIs(FrappeTestCase):
	def test_the_field_is_added_only_when_flow_is_present(self):
		with patch("churchit.ai.flow_models.create_custom_fields") as create:
			with patch("churchit.ai.flow_models.has_flow", return_value=False):
				add_privacy_label_field()
			create.assert_not_called()

			with patch("churchit.ai.flow_models.has_flow", return_value=True):
				add_privacy_label_field()
			create.assert_called_once_with(PRIVACY_LABEL_FIELDS)

	def test_a_frappe_without_flow_has_no_label_field(self):
		if has_flow():
			self.skipTest("This Frappe has Flow.")

		self.assertFalse(frappe.db.exists("Custom Field", {"dt": "Flow Model"}))
		add_privacy_label_field()
		self.assertFalse(frappe.db.exists("Custom Field", {"dt": "Flow Model"}))

	def test_the_hooks_are_wired(self):
		self.assertIn("churchit.ai.flow_models.add_privacy_label_field", frappe.get_hooks("after_migrate"))
		validators = frappe.get_hooks("doc_events")["Flow Model"]["validate"]
		self.assertIn("churchit.ai.flow_models.stamp_privacy_label", validators)

	def test_a_model_saved_before_the_field_exists_is_left_alone(self):
		without_field = SimpleNamespace(meta=SimpleNamespace(has_field=lambda fieldname: False))

		self.assertIsNone(stamp_privacy_label(without_field))

	def test_the_panel_lists_no_model_without_flow(self):
		with patch("churchit.ai.switch.has_flow", return_value=False):
			self.assertEqual(get_flow_model_lines(is_system_manager=True), [])
			self.assertEqual(get_flow_model_lines(is_system_manager=False), [])


class FlowModelTestCase(RollbackEachTest):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if has_flow():
			ensure_user(MANAGER, "Label Manager", roles=("System Manager",))
			ensure_user(OTHER_MANAGER, "Label Other Manager", roles=("System Manager",))

	def setUp(self):
		if not has_flow():
			self.skipTest("This Frappe has no Flow.")
		super().setUp()

	def make_model(self, title: str, **values):
		"""Save a Flow Model. Saving the first one also gives Flow's Assistant a model."""
		model = {"doctype": "Flow Model", "title": title, "model_id": "ollama_chat/test", "enabled": 1}
		return frappe.get_doc({**model, **values}).insert()

	def save_as(self, user: str, model, **values) -> None:
		frappe.set_user(user)
		try:
			model.update(values)
			model.save()
		finally:
			frappe.set_user("Administrator")


class TestLabelField(FlowModelTestCase):
	def test_migrate_adds_the_label_to_the_flow_model_form(self):
		meta = frappe.get_meta("Flow Model")
		label = meta.get_field(LABEL_FIELD)

		self.assertEqual(label.fieldtype, "Select")
		self.assertEqual(meta.get_options(LABEL_FIELD).split("\n"), list(PRIVACY_LABELS))
		self.assertEqual(label.default, DEFAULT_LABEL)
		self.assertTrue(label.description)
		for fieldname in (BY_FIELD, ON_FIELD):
			self.assertTrue(meta.get_field(fieldname).read_only)

	def test_the_label_follows_a_flow_field_that_still_exists(self):
		meta = frappe.get_meta("Flow Model")
		anchor = PRIVACY_LABEL_FIELDS["Flow Model"][0]["insert_after"]
		fieldnames = [field.fieldname for field in meta.fields]

		self.assertTrue(
			frappe.db.exists("DocField", {"parent": "Flow Model", "fieldname": anchor}),
			f"Flow Model lost {anchor}, the field the label follows.",
		)
		self.assertEqual(fieldnames[fieldnames.index(anchor) + 1 :][:3], [LABEL_FIELD, BY_FIELD, ON_FIELD])

	def test_adding_the_field_again_changes_nothing(self):
		def stored():
			return frappe.get_all("Custom Field", filters={"dt": "Flow Model"}, fields=["name", "modified"])

		before = stored()
		add_privacy_label_field()

		ours = {f"Flow Model-{field['fieldname']}" for field in PRIVACY_LABEL_FIELDS["Flow Model"]}
		self.assertLessEqual(ours, {row.name for row in before})
		self.assertEqual(stored(), before)

	def test_a_new_model_is_unknown_and_has_no_stamp(self):
		model = self.make_model("_Test Label New")

		self.assertEqual(frappe.db.get_value("Flow Model", model.name, LABEL_FIELD), "Unknown")
		self.assertEqual(model.get(LABEL_FIELD), "Unknown")
		self.assertIsNone(model.get(BY_FIELD))
		self.assertIsNone(model.get(ON_FIELD))
		self.assertEqual(frappe.new_doc("Flow Model").get(LABEL_FIELD), "Unknown")

	def test_a_copy_of_a_model_starts_unknown(self):
		original = self.make_model("_Test Label Original", **{LABEL_FIELD: "Local"})

		copy = frappe.copy_doc(original, ignore_no_copy=False)
		copy.title = "_Test Label Copy"
		copy.insert()

		self.assertEqual(original.get(LABEL_FIELD), "Local")
		self.assertEqual(copy.get(LABEL_FIELD), "Unknown")
		self.assertIsNone(copy.get(BY_FIELD))


class TestLabelStamp(FlowModelTestCase):
	def test_changing_the_label_stamps_who_and_when(self):
		model = self.make_model("_Test Label Stamp")
		started = now_datetime()

		self.save_as(MANAGER, model, **{LABEL_FIELD: "Zero retention"})

		saved = frappe.get_doc("Flow Model", model.name)
		self.assertEqual(saved.get(LABEL_FIELD), "Zero retention")
		self.assertEqual(saved.get(BY_FIELD), MANAGER)
		self.assertGreaterEqual(saved.get(ON_FIELD), started)

	def test_a_model_made_with_a_label_is_stamped(self):
		model = self.make_model("_Test Label Made", **{LABEL_FIELD: "Local"})

		self.assertEqual(model.get(BY_FIELD), "Administrator")
		self.assertIsNotNone(model.get(ON_FIELD))

	def test_a_save_that_keeps_the_label_keeps_the_stamp(self):
		model = self.make_model("_Test Label Kept", **{LABEL_FIELD: "No training"})
		self.save_as(MANAGER, model, **{LABEL_FIELD: "Local"})
		stamped = frappe.get_doc("Flow Model", model.name)

		self.save_as(OTHER_MANAGER, stamped, enabled=0)

		saved = frappe.get_doc("Flow Model", model.name)
		self.assertEqual(saved.get(LABEL_FIELD), "Local")
		self.assertEqual(saved.get(BY_FIELD), MANAGER)
		self.assertEqual(saved.get(ON_FIELD), stamped.get(ON_FIELD))

	def test_the_next_change_is_stamped_by_the_next_person(self):
		model = self.make_model("_Test Label Next")
		self.save_as(MANAGER, model, **{LABEL_FIELD: "Local"})

		self.save_as(OTHER_MANAGER, frappe.get_doc("Flow Model", model.name), **{LABEL_FIELD: "May train"})

		saved = frappe.get_doc("Flow Model", model.name)
		self.assertEqual(saved.get(LABEL_FIELD), "May train")
		self.assertEqual(saved.get(BY_FIELD), OTHER_MANAGER)

	def test_a_save_cannot_rewrite_the_stamp(self):
		model = self.make_model("_Test Label Forged", **{LABEL_FIELD: "Local"})
		stamped = frappe.get_doc("Flow Model", model.name)
		stamped_on = stamped.get(ON_FIELD)

		self.save_as(
			MANAGER, stamped, **{BY_FIELD: OTHER_MANAGER, ON_FIELD: "2020-01-01 00:00:00", "enabled": 0}
		)

		saved = frappe.get_doc("Flow Model", model.name)
		self.assertEqual(saved.get(BY_FIELD), "Administrator")
		self.assertEqual(saved.get(ON_FIELD), stamped_on)

	def test_a_new_unknown_model_cannot_come_with_a_stamp(self):
		model = self.make_model("_Test Label Fresh", **{BY_FIELD: MANAGER, ON_FIELD: "2020-01-01 00:00:00"})

		self.assertEqual(model.get(LABEL_FIELD), "Unknown")
		self.assertIsNone(model.get(BY_FIELD))
		self.assertIsNone(model.get(ON_FIELD))


class TestPanelLines(FlowModelTestCase):
	def lines(self, user: str = "Administrator") -> dict[str, dict]:
		frappe.set_user(user)
		try:
			return {line["surface"]: line for line in get_exposure()}
		finally:
			frappe.set_user("Administrator")

	def test_the_panel_lists_each_enabled_model_with_its_label(self):
		frappe.db.set_value("Flow Model", {"enabled": 1}, "enabled", 0)
		self.make_model("_Test Panel Plain")
		self.make_model("_Test Panel Trains", **{LABEL_FIELD: "May train"})
		self.make_model("_Test Panel Local", **{LABEL_FIELD: "Local"}, embedding=1)
		self.make_model("_Test Panel Off", **{LABEL_FIELD: "Zero retention"}, enabled=0)

		lines = self.lines()

		self.assertEqual(lines["Flow model: _Test Panel Plain"]["state"], "Unknown")
		self.assertTrue(lines["Flow model: _Test Panel Plain"]["open"])
		self.assertIn("Privacy Label", lines["Flow model: _Test Panel Plain"]["note"])
		self.assertEqual(
			lines["Flow model: _Test Panel Plain"]["link"], f"/app/flow-model/{quote('_Test Panel Plain')}"
		)
		self.assertEqual(lines["Flow model: _Test Panel Trains"]["state"], "May train")
		self.assertTrue(lines["Flow model: _Test Panel Trains"]["open"])
		self.assertIn("may train", lines["Flow model: _Test Panel Trains"]["note"])
		self.assertEqual(lines["Flow embedding model: _Test Panel Local"]["state"], "Local")
		self.assertFalse(lines["Flow embedding model: _Test Panel Local"]["open"])
		self.assertNotIn("Flow model: _Test Panel Off", lines)
		self.assertNotIn("Flow models", lines)

	def test_a_model_without_a_stored_label_reads_unknown(self):
		frappe.db.set_value("Flow Model", {"enabled": 1}, "enabled", 0)
		model = self.make_model("_Test Panel Blank")
		frappe.db.set_value("Flow Model", model.name, LABEL_FIELD, None)

		self.assertEqual(self.lines()["Flow model: _Test Panel Blank"]["state"], "Unknown")

	def test_the_panel_works_before_migrate_adds_the_field(self):
		frappe.db.set_value("Flow Model", {"enabled": 1}, "enabled", 0)
		self.make_model("_Test Panel Early", **{LABEL_FIELD: "Local"})
		meta = frappe.get_meta("Flow Model")
		has_field = meta.has_field

		with patch.object(
			meta, "has_field", lambda fieldname: fieldname != LABEL_FIELD and has_field(fieldname)
		):
			line = self.lines()["Flow model: _Test Panel Early"]

		self.assertEqual(line["state"], "Unknown")
		self.assertTrue(line["open"])

	def test_the_panel_says_when_no_model_is_enabled(self):
		frappe.db.set_value("Flow Model", {"enabled": 1}, "enabled", 0)

		line = self.lines()["Flow models"]

		self.assertEqual(line["state"], "None enabled")
		self.assertFalse(line["open"])

	def test_a_church_manager_is_sent_to_a_system_manager(self):
		frappe.db.set_value("Flow Model", {"enabled": 1}, "enabled", 0)
		self.make_model("_Test Panel Hidden", **{LABEL_FIELD: "Local"})
		manager = ensure_user(CHURCH_MANAGER, "Label Church Manager", roles=("Church Manager",))

		lines = self.lines(manager)

		self.assertEqual(lines["Flow models"]["state"], "Ask a System Manager")
		self.assertNotIn("_Test Panel Hidden", frappe.as_json(lines))

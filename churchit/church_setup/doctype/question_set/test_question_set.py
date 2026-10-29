# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

import frappe
from frappe.tests.utils import FrappeTestCase

from churchit.tests.helpers import assert_scoped, ensure_user, make_person, make_two_churches
from churchit.tests.test_questions import make_question_set


class TestQuestionSet(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_root, cls.branch_a, cls.branch_b = make_two_churches()
		cls.addClassCleanup(frappe.clear_cache)
		cls.manager_a = ensure_user(
			"_test_questions_manager_a@example.com", "QuestionsA", roles=("Church Manager",)
		)
		make_person("_Test Questions Manager", "A", church=cls.branch_a, user=cls.manager_a)

	def test_a_church_sees_only_its_own_question_sets(self):
		mine = make_question_set("_Test Scope Questions A", church=self.branch_a).name
		theirs = make_question_set("_Test Scope Questions B", church=self.branch_b).name

		assert_scoped(self, "Question Set", self.manager_a, mine, theirs)

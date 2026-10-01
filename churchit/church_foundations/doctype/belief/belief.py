# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from frappe.website.website_generator import WebsiteGenerator

from churchit.scripture import format_reference


class Belief(WebsiteGenerator):
	def validate(self):
		super().validate()
		self.bible_references = format_reference(self.bible_references)

# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

from frappe.utils import add_days, get_year_start, today

from churchit.church_finances.dashboard_chart_source.giving_by_fund import giving_by_fund
from churchit.church_finances.report.first_time_givers.test_first_time_givers import give
from churchit.tests.helpers import RollbackEachTest, ensure


class TestGivingByFund(RollbackEachTest):
	def test_only_this_years_giving_counts(self):
		cash = ensure("Payment Type", {"type": "Cash"})
		this_year = ensure("Fund", {"fund": "_Test Giving This Year"})
		last_year = ensure("Fund", {"fund": "_Test Giving Last Year"})
		new_years_day = get_year_start(today())
		give(
			f"{add_days(new_years_day, -1)} 23:59:00",
			[{"fund": last_year, "payment_type": cash, "amount": 900000}],
		)
		give(f"{new_years_day} 00:00:00", [{"fund": this_year, "payment_type": cash, "amount": 800000}])

		chart = giving_by_fund.get()

		totals = dict(zip(chart["labels"], chart["datasets"][0]["values"], strict=True))
		self.assertEqual(totals.get("_Test Giving This Year"), 800000)
		self.assertNotIn("_Test Giving Last Year", totals)

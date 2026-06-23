frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["Fund Goal Progress"] = {
	method: "church.church_finances.dashboard_chart_source.fund_goal_progress.fund_goal_progress.get",
};

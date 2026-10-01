frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["People Added"] = {
	method: "churchit.church_people.dashboard_chart_source.people_added.people_added.get",
};

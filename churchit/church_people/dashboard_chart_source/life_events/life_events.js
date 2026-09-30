frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["Life Events"] = {
	method: "churchit.church_people.dashboard_chart_source.life_events.life_events.get",
};

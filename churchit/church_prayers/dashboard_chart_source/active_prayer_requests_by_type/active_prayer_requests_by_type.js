frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["Active Prayer Requests by Type"] = {
	method: "churchit.church_prayers.dashboard_chart_source.active_prayer_requests_by_type.active_prayer_requests_by_type.get",
};

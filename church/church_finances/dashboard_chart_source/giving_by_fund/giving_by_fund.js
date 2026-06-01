frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["Giving by Fund"] = {
	method: "church.church_finances.dashboard_chart_source.giving_by_fund.giving_by_fund.get",
};

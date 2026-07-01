frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["Finance Summary"] = {
	method: "churchit.church_finances.dashboard_chart_source.finance_summary.finance_summary.get",
};

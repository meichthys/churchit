// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

window.church = window.church || {};

// Name tag printing shared by the Check-In Station and the Person / Function
// Check-In lists. The server renders the tags for the printing method chosen
// in Check-In Settings; this gets them onto paper from the browser side.
church.name_tags = {
	method: "churchit.church_ministries.doctype.function_check_in.function_check_in.print_name_tags",

	// args: { check_ins: [...] } or { persons: [...] }
	print_for(args) {
		return frappe
			.call({ method: church.name_tags.method, args })
			.then((r) => r.message && church.name_tags.print(r.message));
	},

	print(job) {
		if (job.printed) {
			church.name_tags.notify(job.count);
			return Promise.resolve();
		}
		const senders = {
			Browser: church.name_tags.print_in_browser,
			"Zebra Browser Print": church.name_tags.print_with_zebra,
			"QZ Tray": church.name_tags.print_with_qz,
		};
		return senders[job.method](job).catch((error) => {
			frappe.msgprint({
				title: __("Name tags did not print"),
				indicator: "red",
				message: error.message || String(error),
			});
		});
	},

	notify(count) {
		frappe.show_alert({
			message: __("{0} name tag(s) sent to the printer.", [count]),
			indicator: "green",
		});
	},

	// Any printer with a driver. Chrome started with --kiosk-printing prints silently.
	print_in_browser(job) {
		return new Promise((resolve) => {
			const frame = document.createElement("iframe");
			frame.style.cssText = "position:fixed;right:0;bottom:0;width:0;height:0;border:0;";
			frame.srcdoc = job.content;
			frame.onload = () => {
				const win = frame.contentWindow;
				win.onafterprint = () => frame.remove();
				setTimeout(() => frame.remove(), 5 * 60 * 1000);
				win.focus();
				win.print();
				resolve();
			};
			document.body.appendChild(frame);
		});
	},

	// Zebra's free Browser Print app listens on localhost and asks once to trust this site.
	async print_with_zebra(job) {
		const base = "http://localhost:9100";
		const device = await fetch(`${base}/default?type=printer`)
			.then((response) => response.json())
			.catch(() => {
				throw new Error(
					__(
						"Zebra Browser Print is not running on this computer, or has not accepted this site yet."
					)
				);
			});
		if (!device || !device.name) {
			throw new Error(
				__("Zebra Browser Print has no default printer. Open it and choose one.")
			);
		}
		const response = await fetch(`${base}/write`, {
			method: "POST",
			body: JSON.stringify({ device, data: job.content }),
		});
		if (!response.ok) {
			throw new Error(
				__("Zebra Browser Print rejected the labels ({0}).", [response.status])
			);
		}
		church.name_tags.notify(job.count);
	},

	// QZ Tray, through the client frappe already ships for raw printing.
	print_with_qz(job) {
		return frappe.ui.form
			.qz_connect()
			.then(() => job.printer_name || qz.printers.getDefault())
			.then((printer) => qz.print(qz.configs.create(printer), [job.content]))
			.then(() => church.name_tags.notify(job.count));
	},
};

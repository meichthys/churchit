// Auto-apply function filter when report loads
frappe.after_ajax(() => {
	setTimeout(() => {
		// Get function from URL parameters if available
		const urlParams = new URLSearchParams(window.location.search);
		const functionParam = urlParams.get('function');

		if (functionParam) {
			// Find and set the function filter input
			const functionFilterInput = document.querySelector('input[data-fieldname="function"]');
			if (functionFilterInput) {
				functionFilterInput.value = functionParam;
				functionFilterInput.dispatchEvent(new Event('change', { bubbles: true }));

				// Trigger report refresh
				const refreshBtn = document.querySelector('button.btn-primary[data-label="Refresh"]');
				if (refreshBtn) {
					refreshBtn.click();
				}
			}
		}
	}, 500);
});

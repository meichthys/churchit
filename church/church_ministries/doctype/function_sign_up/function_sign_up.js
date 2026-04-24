// Copyright (c) 2026, meichthys and contributors
// For license information, please see license.txt

frappe.ui.form.on("Function Sign-Up", {
	refresh(frm) {
		// Hide quantity_signed_up column only on new Function Sign-Up forms
        setTimeout(() => {
            // Check if we're on the Function Sign-Up form (not Function form)
            if (frm.doctype === "Function Sign-Up") {
                // Add a unique marker to the grid wrapper
                const gridWrapper = frm.fields_dict.table_iprj.wrapper;
                if (gridWrapper) {
                    gridWrapper.setAttribute("data-form-type", "function-sign-up");
                    const style = document.createElement("style");
                    style.textContent = `
                        [data-form-type="function-sign-up"] [data-fieldname="quantity_signed_up"] {
                            display: none !important;
                            width: 0 !important;
                        }
                    `;
                    document.head.appendChild(style);
                }
            }
        }, 100);
    }
});

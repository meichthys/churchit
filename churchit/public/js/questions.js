// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

// Shows the questions of a Question Set in a desk Dialog or on a Web Form page. The fields come from
// churchit.questions.get_fields on the server; read the answers with the returned group's get_values().
(function () {
	window.churchit = window.churchit || {};
	churchit.questions = {
		render(wrapper, fields) {
			const group = new frappe.ui.FieldGroup({ parent: $(wrapper), fields: fields });
			group.make();
			return group;
		},
	};
})();

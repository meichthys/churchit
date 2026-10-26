// This source code is freely given for the sake of the gospel (Matthew 10:8)
// and is licensed under MIT No Attribution (MIT-0).

frappe.ready(function () {
	const web_form = frappe.web_form;
	frappe
		.call({
			method: "churchit.church_setup.doctype.form_response.form_response.get_form",
			type: "GET",
			args: { question_set: frappe.utils.get_query_params().question_set },
		})
		.then((r) => show_questions(web_form, r.message))
		.catch(() => $(".web-form").hide());
});

// The questions draw from the set, and their answers go back as the rows of the Answers
// table, which the server checks against the set again.
function show_questions(web_form, form) {
	$(".web-form-title h1").text(form.title);
	document.title = form.title;

	const answers = web_form.fields_dict.answers;
	const $questions = $("<div>").appendTo(answers.$wrapper);
	const group = churchit.questions.render($questions, form.fields);
	web_form.validate = () => {
		const values = group.get_values(true);
		answers.df.data = Object.entries(values).map(([question, answer]) => ({
			question,
			answer,
		}));
		return true;
	};

	if (form.price) {
		// A priced form goes on to the payment page once the response is saved.
		const show_success = web_form.handle_success.bind(web_form);
		web_form.handle_success = (response) => {
			show_success(response);
			frappe
				.call({
					method: "churchit.church_setup.doctype.form_response.form_response.pay",
					args: { response: response.name },
				})
				.then((r) => (window.location.href = r.message));
		};
	}
}

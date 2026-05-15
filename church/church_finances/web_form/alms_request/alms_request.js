frappe.ready(function() {
	var recipient_ctrl = frappe.web_form.fields_dict['recipient'];
	var type_ctrl      = frappe.web_form.fields_dict['recipient_type'];

	if (recipient_ctrl && type_ctrl) {
		var $input    = recipient_ctrl.$input;
		var $wrap     = recipient_ctrl.$wrapper;
		var real_name = frappe.web_form.doc && frappe.web_form.doc.recipient || '';

		// Override get_value so the form submits the document name, not the display label
		var original_get_value = recipient_ctrl.get_value.bind(recipient_ctrl);
		recipient_ctrl.get_value = function() {
			return real_name || original_get_value();
		};

		// Custom dropdown for searching recipients by label
		var $dd = $('<ul>').css({
			position:     'absolute',
			background:   '#fff',
			border:       '1px solid #d1d8dd',
			borderRadius: '0 0 4px 4px',
			boxShadow:    '0 4px 8px rgba(0,0,0,0.1)',
			listStyle:    'none',
			padding:      0,
			margin:       0,
			maxHeight:    '180px',
			overflowY:    'auto',
			zIndex:       9999,
			display:      'none',
			left:         0,
			right:        0
		});
		$wrap.css('position', 'relative').append($dd);

		var timer;
		function search(term) {
			var doctype = type_ctrl.get_value();
			if (!doctype) { $dd.empty().hide(); return; }

			clearTimeout(timer);
			timer = setTimeout(function() {
				frappe.call({
					method: 'church.church_website.api.search_church_recipient',
					args: { doctype: doctype, txt: term || '' },
					callback: function(r) {
						$dd.empty().hide();
						var results = r.message || [];
						results.forEach(function(d) {
							$('<li>').text(d.label)
								.css({ padding: '6px 12px', cursor: 'pointer' })
								.hover(
									function() { $(this).css('background', '#f4f5f7'); },
									function() { $(this).css('background', '#fff'); }
								)
								.on('mousedown', function(e) {
									e.preventDefault();
									real_name = d.name;
									$input.val(d.label);
									$dd.hide();
								})
								.appendTo($dd);
						});
						if (results.length) $dd.show();
					}
				});
			}, 250);
		}

		$input.on('input', function() { real_name = ''; search($(this).val()); });
		$input.on('focus', function() { search($(this).val()); });
		$input.on('blur',  function() { setTimeout(function() { $dd.hide(); }, 200); });

		frappe.web_form.on('recipient_type', function() {
			real_name = '';
			$input.val('');
			$dd.empty().hide();
		});

		// On edit, the server resolves recipient to its title; map it back to the doc name
		if (real_name && frappe.web_form.doc.recipient_type) {
			frappe.call({
				method: 'church.church_website.api.search_church_recipient',
				args: { doctype: frappe.web_form.doc.recipient_type, txt: real_name },
				callback: function(r) {
					var results = r.message || [];
					for (var i = 0; i < results.length; i++) {
						if (results[i].name === real_name || results[i].label === real_name) {
							real_name = results[i].name;
							$input.val(results[i].label);
							break;
						}
					}
				}
			});
		}

		// On new forms, default recipient and requestor to the current user's Person record
		if (!frappe.web_form.doc.name) {
			frappe.call({
				method: 'frappe.client.get_value',
				args: {
					doctype: 'Person',
					filters: { user: frappe.session.user },
					fieldname: ['name', 'full_name']
				},
				callback: function(r) {
					if (!r.message || !r.message.name) return;
					var person_name  = r.message.name;
					var person_label = r.message.full_name || person_name;

					var requestor_ctrl = frappe.web_form.fields_dict['requestor'];
					if (requestor_ctrl) requestor_ctrl.set_value(person_name);

					// Setting recipient_type fires our change handler which clears state;
					// assign real_name/input afterwards so they aren't clobbered.
					Promise.resolve(type_ctrl.set_value('Person')).then(function() {
						real_name = person_name;
						$input.val(person_label);
					});
				}
			});
		}
	}
});

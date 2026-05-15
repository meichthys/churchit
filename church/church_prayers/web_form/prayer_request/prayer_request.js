frappe.ready(function() {
	var name_ctrl = frappe.web_form.fields_dict['recipient_name'];
	var type_ctrl = frappe.web_form.fields_dict['recipient_type'];

	// Guard: If fields don't exist OR if we are in read-only mode (no $input)
	if (!name_ctrl || !type_ctrl || !type_ctrl.$input) {
		console.log("Web Form is in read-only mode; skipping search initialization.");
		return;
	}

	var $type_select = type_ctrl.$input;
	var $input       = name_ctrl.$input;
	var $wrap        = name_ctrl.$wrapper;

	// Make recipient_name editable so the user can search
	name_ctrl.df.read_only = 0;
	name_ctrl.refresh();

	// Initialise the input with the already-resolved display name
	if (frappe.web_form.doc && frappe.web_form.doc.recipient_name) {
		$input.val(frappe.web_form.doc.recipient_name);
	}

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
								$input.val(d.label);
								$dd.hide();
								frappe.web_form.set_value('recipient', d.name);
								frappe.web_form.set_value('recipient_type', type_ctrl.get_value());
							})
							.appendTo($dd);
					});
					if (results.length) $dd.show();
				}
			});
		}, 250);
	}

	$input.on('input', function() { search($(this).val()); });
	$input.on('focus', function() { search($(this).val()); });
	$input.on('blur',  function() { setTimeout(function() { $dd.hide(); }, 200); });

	frappe.web_form.on('recipient_type', function() {
		$input.val('');
		frappe.web_form.set_value('recipient', '');
		$dd.empty().hide();
	});

	// Populate recipient_type with church app doctypes, then handle defaults
	frappe.call({
		method: 'church.church_website.api.get_church_doctypes',
		args: {},
		callback: function(r) {
			// CHECK: If the input doesn't exist (read-only mode), just stop here.
			if (!type_ctrl || !type_ctrl.$input) {
				console.log("Input field not found. Likely in read-only mode.");
				return;
			}

			// Use the actual controller input directly to be safe
			var $el = type_ctrl.$input;

			$el.empty().append($('<option value="">').text(''));
			(r.message || []).forEach(function(d) {
				$el.append($('<option>').val(d.name).text(d.name));
			});

			var existing = frappe.web_form.doc && frappe.web_form.doc.recipient_type;
			if (existing) {
				$el.val(existing);
			} else if (!frappe.web_form.doc.name) {
				auto_fill_current_user();
			}
		}
	});

	// On new forms, default recipient_type/recipient/recipient_name/requestor to the current user's Person record
	function auto_fill_current_user() {
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
				// assign recipient/recipient_name afterwards so they aren't clobbered.
				$type_select.val('Person');
				Promise.resolve(frappe.web_form.set_value('recipient_type', 'Person')).then(function() {
					frappe.web_form.set_value('recipient', person_name);
					frappe.web_form.set_value('recipient_name', person_label);
					$input.val(person_label);
				});
			}
		});
	}
});

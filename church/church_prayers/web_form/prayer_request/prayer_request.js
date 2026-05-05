// Runs inside frappe.init_client_script() — fields are already rendered
var recip_ctrl = frappe.web_form.fields_dict['recipient'];
var type_ctrl = frappe.web_form.fields_dict['recipient_type'];

if (recip_ctrl && type_ctrl) {
	// Populate recipient_type with church app doctypes from the server
	frappe.call({
		method: 'church.church_website.api.get_church_doctypes',
		args: {},
		callback: function(r) {
			var $select = type_ctrl.$input;
			$select.empty().append($('<option value="">').text(''));
			(r.message || []).forEach(function(d) {
				$select.append($('<option>').val(d.name).text(d.name));
			});
			// Restore value if editing an existing record
			var existing = frappe.web_form.doc && frappe.web_form.doc.recipient_type;
			if (existing) $select.val(existing);
		}
	});

	var $input = recip_ctrl.$input;
	var $wrap = recip_ctrl.$wrapper;
	var real_name = frappe.web_form.doc && frappe.web_form.doc.recipient || '';

	// Override get_value so the form submits the document name, not the display label
	var original_get_value = recip_ctrl.get_value.bind(recip_ctrl);
	recip_ctrl.get_value = function() {
		return real_name || original_get_value();
	};

	// Build custom dropdown for recipient
	var $dd = $('<ul>').css({
		position: 'absolute',
		background: '#fff',
		border: '1px solid #d1d8dd',
		borderRadius: '0 0 4px 4px',
		boxShadow: '0 4px 8px rgba(0,0,0,0.1)',
		listStyle: 'none',
		padding: 0,
		margin: 0,
		maxHeight: '180px',
		overflowY: 'auto',
		zIndex: 9999,
		display: 'none',
		left: 0,
		right: 0
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

	// When user types, clear the stored name so search uses their input
	$input.on('input', function() { real_name = ''; search($(this).val()); });
	$input.on('focus', function() { search($(this).val()); });
	$input.on('blur', function() { setTimeout(function() { $dd.hide(); }, 200); });

	frappe.web_form.on('recipient_type', function() {
		real_name = '';
		$input.val('');
		$dd.empty().hide();
	});

	// Resolve label for existing recipient value
	if (real_name && frappe.web_form.doc.recipient_type) {
		frappe.call({
			method: 'church.church_website.api.search_church_recipient',
			args: { doctype: frappe.web_form.doc.recipient_type, txt: '' },
			callback: function(r) {
				var results = r.message || [];
				for (var i = 0; i < results.length; i++) {
					if (results[i].name === real_name) {
						$input.val(results[i].label);
						break;
					}
				}
			}
		});
	}
}

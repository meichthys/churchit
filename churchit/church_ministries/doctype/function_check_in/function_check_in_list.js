
// Add a message to explain how to do bulk-check-ins
frappe.listview_settings['Function Check-In'] = {
    onload(listview) {
        listview.page.add_inner_message(
            `<div style="background: var(--yellow-highlight-color); padding: \
            8px 12px; border-radius: 6px; display: inline-block;">
                💡 Tip: To do bulk Check-Ins, open the <a href="/app/person">\
                <strong>Person list</strong></a>, select the people you want \
                to check-in and choose <i>Actions → Check In</i>
            </div>`
        );
    }
};
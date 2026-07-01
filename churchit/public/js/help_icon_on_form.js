
// Use jQuery since we cannot use a wildcard doctype
$(document).on('form-refresh', function(e, frm) {
    if (frm && frm.meta && frm.meta.documentation) {
        frm.page.add_action_icon(
            'help',
            () => window.open(frm.meta.documentation, '_blank'),
            '',
            __('Documentation')
        );
    }
});
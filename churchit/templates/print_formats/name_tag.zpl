{#- ZPL name tag for a Function Check-In, sized from `settings` (Check-In Settings). With
    `pickup_names` set it renders the family's pickup tag instead. ^ and ~ are ZPL control
    characters, so they are stripped from names. -#}
{%- set settings = settings or frappe.get_doc("Check-In Settings") -%}
{%- set dpi = (settings.label_dpi or 203)|int -%}
{%- set width = ((settings.label_width or 4) * dpi)|int -%}
{%- set height = ((settings.label_height or 2) * dpi)|int -%}
{%- set pad = (width * 0.05)|int -%}
{%- set inner = width - 2 * pad -%}
{%- set person = frappe.db.get_value("Person", doc.person, ["first_name", "last_name"], as_dict=True) if doc.person else None -%}
{%- set function = frappe.db.get_value("Function", doc.function, ["function_name", "start_date"], as_dict=True) if doc.function else None -%}
{%- set first_name = ((person.first_name if person else "") or "")|replace("^", "")|replace("~", "") -%}
{%- set last_name = ((person.last_name if person else "") or "")|replace("^", "")|replace("~", "") -%}
{%- set footer = ([function.function_name if function else "", frappe.utils.formatdate(function.start_date, "MMM d, yyyy") if function and function.start_date else ""]|select|join(" - "))|replace("^", "")|replace("~", "") -%}
{%- set code = doc.security_code or "" -%}
{%- set code_width = (height * 0.16 * 0.6 * 5)|int if code else 0 -%}
{%- set first_size = [(height * 0.32)|int, (inner / (0.55 * [first_name|length, 1]|max))|int]|min -%}
^XA
^CI28
^PW{{ width }}
^LL{{ height }}
^LH0,0
{%- if pickup_names %}
^FO{{ pad }},{{ (height * 0.08)|int }}^A0N,{{ (height * 0.1)|int }},{{ (height * 0.1)|int }}^FB{{ inner }},1,0,C^FDPICKUP^FS
^FO{{ pad }},{{ (height * 0.2)|int }}^A0N,{{ (height * 0.32)|int }},{{ (height * 0.32)|int }}^FB{{ inner }},1,0,C^FD{{ code }}^FS
^FO{{ pad }},{{ (height * 0.58)|int }}^A0N,{{ (height * 0.1)|int }},{{ (height * 0.1)|int }}^FB{{ inner }},2,0,C^FD{{ pickup_names|join(", ")|replace("^", "")|replace("~", "") }}^FS
^FO{{ pad }},{{ (height * 0.86)|int }}^A0N,{{ (height * 0.07)|int }},{{ (height * 0.07)|int }}^FB{{ inner }},1,0,C^FD{{ footer }}^FS
{%- else %}
^FO{{ pad }},{{ (height * 0.14)|int }}^A0N,{{ first_size }},{{ first_size }}^FB{{ inner }},1,0,C^FD{{ first_name }}^FS
^FO{{ pad }},{{ (height * 0.52)|int }}^A0N,{{ (height * 0.14)|int }},{{ (height * 0.14)|int }}^FB{{ inner }},1,0,C^FD{{ last_name }}^FS
^FO{{ pad }},{{ (height * 0.86)|int }}^A0N,{{ (height * 0.07)|int }},{{ (height * 0.07)|int }}^FB{{ inner - code_width }},1,0,L^FD{{ footer }}^FS
{%- if code %}
^FO{{ width - pad - code_width }},{{ (height * 0.76)|int }}^A0N,{{ (height * 0.16)|int }},{{ (height * 0.16)|int }}^FB{{ code_width }},1,0,R^FD{{ code }}^FS
{%- endif %}
{%- endif %}
^PQ1
^XZ

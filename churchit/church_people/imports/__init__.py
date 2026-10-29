# This source code is freely given for the sake of the gospel (Matthew 10:8)
# and is licensed under MIT No Attribution (MIT-0).

"""People imports through Frappe's Data Import.

Each import source is a virtual DocType in Church People whose fields are the columns of that source's
export, labelled exactly as the export heads them, and a provider registered for it under
`data_import_providers` in hooks.py. Data Import matches the columns from the DocType's meta, maps Link
and Select values, previews, runs and logs the import. The provider (`provider.SourceProvider`) warns
about rows in the preview and turns each row into Address, Family and Person records (`record.py`).

To add a source:

1. A virtual DocType "<System> Import": copy one, keep Churchit's fieldnames for the same meaning
   (`record.PERSON_COLUMNS`, `EMAIL_COLUMNS`, `PHONE_COLUMNS`, `ADDRESS_COLUMNS`, `legacy_id`), and
   label each field with the export's header. A Link field lets the church map its own values.
2. A module here with a `SourceProvider` subclass: its `system`, and `to_record`, which works out what
   the columns do not say directly, such as gender codes and the household.
3. One line in `data_import_providers`.
"""

---
title: Import People
emoji: 📥
sidebar_position: 15
---
When your church moves to Churchit, you can bring your people from another church system or from a spreadsheet. Churchit makes a Person for each row and a Family for each household, and keeps the ID that each person had in the old system. When you import a newer file from the same system, Churchit updates those people instead of adding them again. Church Managers and System Managers can import people.

Each import goes through Frappe's **Data Import** tool, in the Data folder of the People sidebar. It reads the file, shows a preview and adds the people in the background.

:::note[Example]
Your church used Planning Center. You export the people as a CSV file, make a Data Import with the type Planning Center Import, and upload the file. The preview asks you to map the Name Prefix "Mr." to Mr. After the import, 350 people and 140 families are in Churchit, and Possible Duplicates lists 4 pairs to check.
:::

## Import from Planning Center

1. In Planning Center People, open the gear menu and click **Import & Export CSV**, then **Start Export**. Download the CSV file from the email (open the ZIP file if needed).

2. In Churchit, open **Data Imports** in the Data folder and click **Add Data Import**. Set **Document Type** to **Planning Center Import**.

3. For the first import, keep **Import Type** as **Insert New Records**. For a later import, choose **Insert or Update Records**.

4. Save, upload the file without changing it, and click **Next**.

5. Map each value that Churchit does not know to a value of your church, or skip its rows.

6. Click **Import**.

The Household Primary Contact becomes the family's Primary Contact. A person with Child set is a Child, and the others are Adults.

## Import from Rock RMS

Rock RMS cannot export all people at once, so make a report once and export it each time.

1. In Rock, open **Tools**, then **Reports**, and add a report for the Person entity.

2. Add these fields, with each **Column Header** set to the name here: Id, Family Id (the Primary Family Id field), Family Name, Family Role (the Age Classification field), Title, First Name, Nick Name, Middle Name, Last Name, Suffix, Gender, Birthdate, Anniversary Date, Marital Status, Connection Status, Record Status, Inactive Reason, Is Deceased, Email, Mobile Phone, Home Phone, Work Phone, Home Address Street 1, Home Address Street 2, Home Address City, Home Address State, Home Address Postal Code and Home Address Country. Id, Family Id and First Name are required.

3. Run the report and click **Export to Excel**.

4. In Churchit, add a Data Import with **Document Type** **Rock RMS Import**, as for Planning Center.

5. Map the values that Churchit does not know, for example the Connection Status Attendee to Regular Attender, and click **Import**.

Rock has no head of household, so Churchit makes the first Adult of each family its Primary Contact. You can change it on the Family.

## Import from Breeze

1. In Breeze, click the gear icon, then **Manage Account**, **View More** and **Export**. Choose **People** and download the spreadsheet.
2. Make sure that the Birthdate column uses the format mm/dd/yyyy.
3. In Churchit, add a Data Import with **Document Type** **Breeze Import**, as for Planning Center, and upload the file without other changes.
4. Map each Status to a Membership, for example Attender to Regular Attender, and click **Import**.

The Head of Household becomes the Primary Contact. A Child is a Child, and a Spouse or Adult is an Adult. For other people, Churchit uses the age: an adult age makes an Other Adult. Set the remaining roles on the Family.

## Import from a spreadsheet

1. Add a Data Import with **Document Type** **People Import**, save, and click **Download Template**. The usual columns are ticked. Tick more if you need them, such as Envelope Number or Medical Notes.

2. Put one person on each row, with a **Person ID**. Give the people of one household the same **Household ID**. Set **Primary Contact** to Yes for one person of each household, and **Household Role** to Adult, Other Adult or Child.

3. If the people come from another system, type its name in **Imported From**.

4. Upload the file, check the preview and click **Import**.

## The preview and after the import

- A row that cannot be imported stops the import, for example a row with no first name, or an address with a country that Churchit does not know. Correct the file, or click **Skip Row**. A value that Churchit does not know stops the import until you map it. A note, such as an invalid email that Churchit leaves out, does not stop it.

- The same person twice in a file is imported once, with a note.

- An update changes only the fields that have a value in the file. It adds new emails, phones and addresses and keeps the old ones. **Update Existing Records** updates only people imported before.

- Each imported person has the Source Import, and Imported From and Imported ID show where they came from.

- Churchit compares each new person with the people already there and adds Possible Duplicates. Review them and merge the people who are the same.

When AI is turned on, **Suggest Mapping** at the top right of a Data Import matches the headings that Churchit does not know to its fields. Only the headings go to the AI, never a row. Check each pair, click **Use This Mapping**, and save.

## Undo an import

To remove the people and families that one import added, for example after an import with wrong columns, do it soon, before people add attendance or gifts to the new records. You need the right to delete people and families, which a Church Manager has.

1. Open the [People](person.md) list and filter on **Source** equals Import, **Imported From** equals the system, and **Created On** the day of the import. Make sure the list shows everyone (click 500 at the bottom).
2. Tick the box in the list header to select all, click **Actions**, then **Delete**, and confirm.
3. Do the same in the [Families](family.md) list.

Frappe does not delete a person that a later record names, such as someone who attended a function after the import, and it does not delete a family that still has a person. It lists what it did not delete.

More than 10 records are deleted in the background, with a message when it is done. The addresses of deleted families stay in the Address list, where a System Manager can delete them.

:::caution[Undoing an update import]
The undo does not change back the people that an update import changed.
:::

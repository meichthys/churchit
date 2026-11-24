---
title: Import giving history
emoji: 📥
sidebar_position: 5
---
You can add past gifts from another church system, a spreadsheet or your payment processor. Church Finance users, Church Managers and System Managers can import gifts. Each row of the file is one gift. Churchit puts the gifts of one batch on one date in one draft collection. Check each draft collection and submit it. The gifts count only after you submit. Churchit sends no thank-you email for imported gifts.

## The file

You must fill in **Gift ID**, **Date**, **Amount**, **Fund** and **Payment Type**.

- **Gift ID**: the ID of the gift in the old system, for example a Stripe charge ID. Churchit imports each gift only once.

- **Date** and **Amount**: the date and the full amount that the giver paid.

- **Fund** and **Payment Type**: a fund and a payment type of your church. A Check also needs a **Check Number**.

- **Imported From** and **Person ID**: the system name and the giver's ID from your People import. Leave Imported From blank when you imported the people from a spreadsheet.

- **Email**: finds the giver when the Person ID does not.

- **Batch**: the gifts of one batch and one date go in one collection. Blank uses the name of the import.

- **Notes**: text for the donation.

## Import it

1. In the Setup folder of the sidebar, click **Data Imports**, then **Add Data Import**. Set **Document Type** to **Giving Import** and keep **Insert New Records**.

2. Save, and click **Download Template** to get the columns.

3. Upload your file and click **Next**. Match any column that Churchit does not know, or leave it out.

4. Look at the preview. Correct the rows that cannot be imported, or click **Skip Row**.

5. Click **Import**. Then open [Collections](/desk/collection), filter on **Import Batch**, check each draft collection and submit it.

The preview stops a row when Churchit does not know its fund or payment type, when no person or more than one person has its Person ID or email, when its Gift ID is already in Churchit or earlier in the file, when its payment type is non-cash, or when an online gift with the same amount, date and email is already in Churchit. So a second import of the same file adds nothing.

The preview also stops a row whose fund belongs to another church. A gift whose collection was cancelled can be imported again. When the matching online gift is Pending or Needs Review, record it from the Online Donation, not from the import.

If your church made its own copy of the Donation Acknowledgment notification, set its Condition to doc.donations and not doc.import_batch before you submit imported collections. Otherwise each giver gets an email for each old gift.

## Import gifts from Stripe

Use this for gifts that givers made on Stripe's own pages, such as recurring gifts. Churchit already has the gifts from your Give page.

1. In the Stripe Dashboard, open **Payments**, set the dates and click **Export**.

2. Open the file in a spreadsheet. Delete each row whose Description starts with "Online gift to the" (gifts from your Give page), each row whose Status is not Paid, and each row with an Amount Refunded.

3. Rename the columns id to Gift ID, Created date (UTC) to Date and Customer Email to Email. Keep Amount and delete the other columns.

4. Add the columns Fund and Payment Type, and fill them in on each row. You can add a Batch column, for example with the month.

5. Import the file as above. Stripe gives the date in UTC, so a gift late in the evening can have the next day's date.

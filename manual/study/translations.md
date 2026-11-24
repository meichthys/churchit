---
title: Translations
emoji: 🈚
sidebar_position: 2
---
A Bible Translation holds the whole text of one translation of the Bible, such as the KJV. Every Bible reference in the app is read in a translation: in the Bible reader, on bulletins, on Scripture slides and in Bible Memory. Church Managers add and change translations.

Churchit comes with common English translations:

- The **BSB** (Berean Standard Bible) downloads its text when Churchit is installed.

- The other free translations (the KJV, WEB, ASV, BBE and Douay-Rheims) download their text the first time someone opens them. The first opening can take a little longer.

- Translations that are not free, such as the NIV or the ESV, show the status **No Text** until your church imports its own licensed copy.

A translation is ready to read when its **Status** is **Ready**. A translation that is still Downloading, or whose download Failed, is not offered to readers. If a translation cannot open, the reader shows another one with a short notice. A Ready translation has a **Read** button that opens it in the reader.

## Add a free translation

1. Open **Bible Translations** and click **Add Bible Translation**.

2. Type the **Abbreviation**, such as WEB. This short name shows everywhere in the app.

3. Choose **Free Use Bible API** as the **Text Source**, and type the translation's id from the [Free Use Bible API list](https://bible.helloao.org/api/available_translations.json), such as BSB or eng_kjv.

4. Save. The text downloads by itself within a minute or two, and the Status changes from Downloading to Ready. Churchit fills in the language and the website of the translation if they are empty.

If the download fails, check the id and click **Download Again**. On a free translation that has no text yet, click **Download** to get the text now.

## Import a translation that your church has a license for

For a translation that is under copyright, such as the NIV, ESV or NLT, your church must have a license to use it.

1. Prepare a CSV file with the columns book, chapter, verse and text, one verse to a row.
2. Add a Bible Translation, choose **User Import** as the Text Source and attach the file as a **private** file. Churchit refuses a public file and a file with no verses.
3. Save.

An imported translation is shown only to people who are signed in, never to website visitors. On a public page, such as a published sermon, a passage in an imported translation shows only its reference.

:::note[Example]
Your church has a license for the ESV. You import it from a CSV file and set it as the Default Bible Translation. Members read the ESV in the member portal and on the bulletin. A visitor who opens your website's Bible reader sees a free translation instead.
:::
---
title: Question Sets
emoji: 📋
sidebar_position: 5
---
A Question Set is a list of questions that your church asks people: on a sign-up, on a room booking, or as a form of its own on the website. The answers stay on the record that the person filled in.

:::note[Example]
For the children's camp, you make a Question Set with Child's T-shirt size (a choice of S, M, L), Allergies (a paragraph) and "I agree to the camp rules" (a required tick). You choose it on the camp's Function. Each parent who registers answers the questions for each child, and the Function Registrations report shows every answer in one table.
:::

## Make a question set

Open **Question Sets** (in the Forms folder of the Settings sidebar), click **Add Question Set** and give it a **Title**. Then add one row for each question:

- **Question**: the question as people read it, such as T-shirt size.

- **Answer Type**: a line of text (Data), a paragraph (Small Text), a choice from a list (Select), a tick (Check), a date, a whole number (Int), an email address or a phone number.

- **Required**: tick it when people must answer. A required tick must be ticked, for example to agree to the rules.

- **Choices**: for a Select question, type each choice on a new line.

Each question gets an **Answer Name**, made from the question. Two questions in one set cannot have the same Answer Name. Do not change an Answer Name after people answer, because their answers are kept under it. A question cannot depend on the answer to another question: to ask different people different questions, make a second set.

Each answer keeps the question as it was asked, so a later change to the set does not change old answers. With more than one church, a Question Set belongs to one church. Tick **Shared with All Churches** to let every church use it.

**Describe the Form with AI.** When AI is turned on (see the [Foundations manual](../foundations/README.md)), a new Question Set has the button **Describe the Form**. Type what the form should ask, for example "A camp form: child name, age, T-shirt size, and a tick to agree to the rules", and click **Draft**.

Click **Open Draft** to open the Question Set filled in and not saved. Check each question and save. When a question needs something that no Answer Type can do, such as a file, the AI says that the form cannot be drafted.

## Forms on the website

To use a Question Set as a form on its own, tick **Publish as a Form** in the Website Form section and save. Anyone can then answer it at /form/new?question_set= followed by the name of the set, such as QSET-0001.

Click **Open Form** under Links on the Question Set to open it, and copy its address into a web page, an email or a QR code. The form asks for a first name, a last name and an email address, then the questions. Tick **Members Only** to let only signed-in members answer: their answer is then linked to their own Person.

Each answer is a Form Response, in the Forms folder of the Settings sidebar and on the Connections tab of its Question Set. After a guest sends a form, Churchit finds the person with the same name and email, or adds them as a Visitor with the Source Form. The response then shows **Processed**. A response that stays **New** still needs its person.

To follow up each answer, add the trigger **Form Submitted** to a [Follow-up Workflow](../people/follow-up.md) and choose the Question Set (see [Follow-up](../people/follow-up.md) in the People manual).

**Charge for a form.** Before you charge, remember "Freely you have received; freely give" (Matthew 10:8): a form with no Price is free. To charge, give the Question Set a **Price** and a **Fund**. After a person sends the form, they go to the payment page. When the payment arrives, Churchit records it in a collection and the response shows Paid. After you refund a payment at the payment processor, open the Form Response and click **Record Refund**.

With more than one church, a response belongs to the church of its Question Set. The responses to a shared Question Set are shared too, and the person's own church follows them up.

When you anonymize a person, the answers on their own records are removed. On a sign-up, only their own answers are removed, and the answers of the other people stay.

---
title: AI Setup for System Managers
emoji: 🛠️
sidebar_position: 8
---
This part is for the System Manager, or the IT person who looks after your site. It explains how AI reaches the site and how to set it up safely. Read AI and your church's data first. Frappe and Flow change their AI features often, so check this part at each Frappe update. Facts about outside apps and providers were last checked on November 6 and 7, 2026.

## The AI Access panel

The **AI Access on This Site** panel at the foot of AI Settings lists each way that AI can reach the site, whether it is on, and a link to the setting that owns it. It counts the people who may connect an AI app, lists each app that every desk user may sign in to, and says whether Agent Instructions name the Churchit guide.

On a site with Flow, it also lists who can use Flow, the Flow knowledge sources that read church records, the Flow triggers that are on, each AI model with its Privacy Label, and whether Churchit's agents and the Churchit Manual are ready. The line **Churchit AI actions** turns orange when an AI button would be refused. A Church Manager or other staff see "Ask a System Manager" on the lines that only a System Manager can check.

## Allow outside AI apps (MCP)

Frappe has an **MCP server**: the way an AI app, such as Claude or ChatGPT, signs in to the site as one person and works with that person's permissions. Frappe turns it on for every site. Churchit closes it while Use AI in Churchit is off: an AI app then gets "not found", and System Settings refuses to turn it on.

MCP is one setting for the whole site, so this also closes MCP for other Frappe apps on the site, such as ERPNext. When an install or an update closes MCP, each System Manager gets one notice that names those apps.

After a Church Manager or System Manager turns on AI, a System Manager ticks **Enable MCP** on the AI Agents tab of **System Settings**. Churchit never ticks it. A site that wants MCP for another app, such as ERPNext, turns on AI first.

## Who can connect an AI app

Only a Church Manager, a System Manager or a person with the **Church AI User** role can connect an AI app. Churchit refuses the MCP server to everyone else, whether they come with an app, an API key or their own session.

- To let another person connect an AI app, open their User record and add the Church AI User role. Give it only to people you trust to send what they can read to an AI company. The role opens no record by itself.

- To stop a person, remove the role. Their app is refused at once by MCP, but it keeps its token for the REST API, so also delete their tokens in OAuth Bearer Token.

- An app that registers itself gets these three roles as its Allowed Roles. An app that you add by hand in OAuth Client keeps the roles you give it. Older apps may let every desk user sign in: the AI Access panel lists them. If one is an AI app, set its Allowed Roles to Church Manager, System Manager and Church AI User.

- An **API key** works without MCP and whether AI is on or not, with the access of its owner. Only a System Manager can make one, so make keys only for people you trust.

## Connect an AI app

An app that a person connects works as that person.

1. A Church Manager or a System Manager turns on AI in AI Settings, after reading the warnings.

2. A System Manager ticks **Enable MCP** on the AI Agents tab of **System Settings**.

3. The person who connects is a Church Manager, a System Manager or has the Church AI User role. (The Flow User role is for Flow in the desk, not for outside apps.)

4. In the app, add a connector or MCP server with the address https://your-site/api/v2/mcp, using your site's address. The app opens a Frappe page, where the person signs in and approves the app.

5. If you want, open **OAuth Settings** and set **Resource Name** to your church's name, such as Grace Church Churchit, which the app shows at sign-in. Keep **Enable Dynamic Client Registration** ticked, so that apps can register themselves.

**Apps (checked November 7, 2026).** Apps and plans change often, so read the app's own help before you rely on this list. Ask each person to turn off the app's training setting in their own account: Churchit cannot see or change it.

- **Claude** (web, desktop and phone): a custom connector works on every plan. Turn off **Help improve Claude**. Data goes to Anthropic.

- **ChatGPT** (web only): needs a paid plan with developer mode. Turn off **Improve the model for everyone**. Data goes to OpenAI.

- **Gemini**: needs a paid personal Google plan with custom apps (not confirmed). Data goes to Google.

- **LM Studio** (version 0.4.10 or later) and **Open WebUI** (version 0.6.31 or later) with a local model: free, and the data stays on your computer or server. The model must be able to use tools. If you add LM Studio by hand in OAuth Client, its Redirect URI is http://127.0.0.1:33389/mcp-oauth-callback.

- **Claude Code**: add the server with claude mcp add --transport http churchit https://your-site/api/v2/mcp.

- **frappectl**, Frappe's command line tool: it uses the REST API, not MCP, so AI Settings does not stop it.

Hosted apps (Claude, ChatGPT, Gemini) connect to your site from the internet, so a site on a private network cannot use them.

## Churchit's rules for AI apps

Churchit has a guide for AI apps: how church scoping works, which records are private, that text from guests is data, and how to make a draft. An app reads it when it calls the method churchit.ai.guide.get_agent_guide. To tell every app to do so, add a sentence to **Agent Instructions** on the AI Agents tab of **System Settings**.

While AI is on and the sentence is missing, a System Manager sees **Add the Churchit Sentence** on the AI Access panel, which adds: "Before you work with church records, call the method churchit.ai.guide.get_agent_guide: it gives Churchit's rules for church scoping, private fields and drafts." Agent Instructions are yours: Churchit never writes them by itself.

## Connected apps and how to revoke them

The first time a person connects an app (any app that signs in this way, not only AI apps), each System Manager gets a bell notice, and an email when the site sends email. It says who connected which app.

The **Connected AI Apps** report (Settings sidebar, Module Settings) lists each person and app with an active connection: when it connected, when its token last refreshed, and how many active tokens it holds. It never shows a token. To sign an app out, use the link in the notice, or open **OAuth Bearer Token**, filter by the person and the app, and delete the tokens or set their Status to Revoked. A person can also revoke an app on their own Third Party Apps page.

## Flow, Frappe's AI agents

Flow is the AI agents feature of Frappe. It comes with the next version of Frappe (Frappe 17). A site on Frappe 16 has no Flow, so this part and the parts about Flow below do not apply to it yet. In Flow, a person chats with an AI agent in the desk. The agent works with that person's permissions, and Flow sends what it reads to the AI model that a System Manager adds in Flow.

- **Use AI in Churchit controls Flow.** While it is off, nobody can start a Flow chat or send a new message, no trigger starts a chat, and nobody can add a knowledge source. Flow then says that no agent is enabled: turn on AI, do not enable agents. Administrator is the one exception, because Frappe gives it every right. Never use Flow as Administrator.

- **Who can use Flow.** A person with the **Flow User** role, which a System Manager gives on the person's User record. Give it only to people you trust to send what they can read to an AI company.

- **Frappe's general assistant.** Frappe adds an agent, **frappe/Flow**, that can read, add, change and delete every record the person can. Churchit has no setting for it. To turn it off, open it in the Flow Agent list right after you turn on AI, and clear **Enabled**.

- **Ask before every change.** Each chat has an **Approval Mode**: in **Ask**, the agent asks before every change. In **Auto**, a second AI approves the changes the person asked for. In **Auto-approve**, nobody approves. Churchit starts each new chat that a person opens in Ask, even if the picker shows Auto before the first message. Ask your staff to keep Ask and to read each change.

- **To stop a reply that is changing records**, first clear **Enabled** on its agent in the Flow Agent list, then turn AI off.

## Churchit's agents in Flow

On a site with Flow, Churchit adds three agents: **Church Office**, **Writer** and **Private Work**. Churchit adds them after a System Manager saves an enabled chat model in Flow. Until then, the AI Access panel says "Not ready". Each agent starts on the oldest enabled chat model. A System Manager can change the **Model** of each agent in the Flow Agent form, and an update keeps the choice.

- **Church Office** is the agent for your staff. A person opens Flow (Ctrl+I, or Cmd+I on a Mac) and picks Church Office. It answers with the person's own permissions and never saves a record: for a change, it gives a draft link.

It answers the weekly office questions, makes smart lists, briefs on a person or a group, runs reports, reads the open page and searches the manual (see the [People manual](../people/README.md) and Ask the manual). It has no web search and no memory. If someone shares a Church Office chat, the others see what it read with the owner's permissions: do not share a chat that holds a briefing or private records.

- **Writer** and **Private Work** have no tools. Churchit's AI buttons use them: most buttons use Writer, and a request that holds a private record goes to Private Work. Set the Model of Private Work to one labelled Zero retention or Local.

- **Roles on an agent.** In the Flow Agent form, set **Roles** on each Churchit agent to limit who may use it, for example Church Office to your staff. An agent with no roles is open to every Flow User. A person may use Churchit's AI buttons when they may use the agent that the button needs.

- **Choose a model for Church Office.** It needs a model that can use tools. In our tests on November 7, 2026, small local models in Ollama wrote the tool call as text instead of using it, and a 7B model on a computer without a large graphics card was too slow. For a local model, put {"timeout": 1500, "num_ctx": 16384} in **Extra Params** on the Flow Model. Test the model with a plain question before your staff use it.

- **Limit the spend.** Set **Token Budget** on each Churchit agent: the most tokens that one run may spend (0 means no limit). Also set a monthly limit at the provider (see [Choose an AI provider for Flow](#choose-an-ai-provider-for-flow)).

## Private Records in AI Settings

The **Private Records** part of AI Settings shows on a site with Flow. Its list **Only for Local or Zero Retention Models** names the kinds of records (DocTypes) that Churchit's AI buttons send only through Private Work, and only to a model labelled Zero retention or Local.

The recommended list is: Alms Request, Authorized Pickup, Background Check, Care Assignment, Care Request, Collection, Connection Card, Connection Card Photo, Counseling Case, Giving Import, Giving Statement, Meeting Minutes, Member Transfer, Online Donation, Person Note, Pickup Restriction, Pledge, Prayer, Prayer Request and Visitation Log.

This list decides which model each button needs:

- **Any label**: buttons that send no church record, such as Describe People, Draft with AI on text that you typed or on a published function, Describe the Form, Describe the Process, Suggest Mapping, Translate with AI, Study with AI on a published sermon, and the Weekly AI Note.

- **No training, Zero retention or Local**: buttons that send church records, such as Draft with AI on a function that is not published, Brief Me, Explain, Study with AI on an unpublished sermon or a transcript, Suggest Songs, Suggest Type, Explain Match, Suggest Fixes and Read Card with AI.

- **Zero retention or Local**: buttons that send a private record, such as Draft Note With AI, Find Action Items, connection card photos, the prayer and care suggestions, Explain on a giving report, and Brief Me when it holds a note, a visit, a care request or a gift.

**Use the Recommended List** adds each recommended DocType that is missing and keeps the rows you added. Use it again after an update. To remove a DocType, remove its row and save: Churchit shows an orange note that those records can now go to a model labelled No training. A Church Manager who is limited to some churches cannot remove one. The list limits only Churchit's AI buttons: a Flow chat or an AI app sends what the person reads, whatever the list says.

## Flow triggers

A **Flow Trigger** starts an agent by itself, when a record changes or on a schedule. Its chat runs in Auto-approve, so nobody approves its changes. Only a System Manager can make one.

While AI is off, Churchit refuses to save a trigger that is on, and a trigger that is already on starts no chat but logs an error each time it fires. When you turn on AI, every trigger that is on can start chats at once, so check them first in the AI Access panel.

While AI is on, Churchit warns you, but still saves the trigger, when it watches records that guests or members write: Alms Request, Care Request, Comment, Communication, Connection Card, Form Response, Function Sign-Up, Group File, Group Join Request, Ministry Team Assignment, Ministry Team Block, Online Donation, Person, Prayer, Prayer Request or Room Booking. Their text can hold instructions for the AI.

It also warns when the trigger runs as Administrator, or has no **Run As** user and Administrator owns it. Give a trigger an agent that only reads, and set Run As to a user with only the roles that the trigger needs.

A trigger that another app adds is saved without a warning, and Flow can run it as Administrator: check each one in the AI Access panel. Churchit does not warn about triggers on other personal records, such as Contact and Address. To stop a trigger that logs errors while AI is off, untick Enabled.

:::note[Example]
A trigger that starts an agent each time a Care Request is saved runs without anyone approving it, and a guest's text in the request could tell the AI what to do. Churchit warns you when you save it. Give it a read-only agent and a Run As user with few rights, or do not use it.
:::

## Choose an AI provider for Flow

A System Manager adds each AI model in Flow as a **Flow Model**. Each Flow Model has a **Privacy Label**: your note about who sees what the model is sent. Set it from the provider's terms before anyone uses the model:

- **Unknown**: nobody checked. A new model starts here. Treat it as unsafe.
- **May train**: the provider can train its models on what it receives. Never use it for church data.
- **No training**: the provider does not train on what it receives, but can keep it for a short time.
- **Zero retention**: the provider keeps nothing after it answers.
- **Local**: the model runs on your own computer. Nothing leaves it.

Churchit does not check a label: it is your statement, and the form shows who set it and when. Set it on the Flow Model form in the desk (open each model from the AI Access panel). Set the label of the embedding model too, because it receives the text of each knowledge source.

**Providers (checked November 6, 2026).** Providers change their terms often, so read them again. A DPA is a data processing agreement.

- **A model on your own computer**, such as Ollama, LM Studio or llama.cpp: **Local**. Put its address in **Base URL**. For tool use, pick a model that fits 16 GB of video memory or more. Protect Ollama with a key if it runs on another computer.

- **Cloudflare Workers AI**, free daily allowance: **Zero retention**, with AI Gateway logging off.

- **Groq**, with Zero Data Retention on in its Data Controls: **Zero retention**. Without it, leave **Unknown**.

- **OpenAI, Anthropic and Gemini**, with billing on: **No training**. Each has a DPA.

- **Mistral**, with billing on: **No training** after you turn off training in your account, else **May train**.

- **OpenRouter**, limited to providers with zero data retention ({"provider": {"zdr": true}} in **Extra Params**): **Zero retention**. Without that, turn off training for paid models in your OpenRouter settings and use **No training**.

- **Free tiers that train**, such as the Gemini API free tier, Mistral free and OpenRouter models with :free in the name: **May train**. Never use them for church data.

- **Frappe Cloud AI credits**: **Unknown**. Frappe has published no data terms for them.

**Churches in the EU or the UK.** Church records can show religious belief, which the law protects with extra care. Sign the provider's DPA before you send personal data, and ask your data protection adviser whether you need a data protection impact assessment (DPIA) first.

**Set a spend limit.** A hosted model bills each call, and Flow has no monthly limit of its own. Set one at the provider, for example in OpenAI (Organization limits, then Spend: tick **Enforce a hard limit**), Anthropic (Console, Billing, Spend limits), Gemini (AI Studio, Spend), Mistral (Admin Panel, Billing), Groq (Console, Settings, Billing, Limits) or OpenRouter (a Key limit with a monthly reset). Cloudflare's Free plan stops at the daily allowance.

## Flow knowledge

A **Flow Knowledge Base** holds text that an agent can search. A **Flow Knowledge Source** with the Source Type DocType fills it with copies of records, and Flow does **not** check who may read each record: anyone who can use an agent with that knowledge can read the copied text. Flow also sends the text to its embedding model, and copies changed records again each day when **Auto Sync** is on.

So Churchit blocks the records that hold data about people. **Blocked from Flow Knowledge**, in the Flow Knowledge part of AI Settings, lists the DocTypes that a knowledge source may not read: the Churchit records about people, such as Person, Family, Prayer Request, Counseling Case, Counseling Session and Donation, and Frappe's Access Log, Activity Log, Address, Comment, Communication, Contact, Data Import Log, Deleted Document, Email Group Member, Email Queue, Error Log, Event, File, Notification Log, ToDo, User and Version, with their child tables. On a site with Flow, it also holds Flow's own records of chats and knowledge: Flow Agent Memory, Flow Knowledge Chunk, Flow Run, Flow Session, Flow Session Attachment and Flow Session Message.

Churchit refuses to save a source that reads a blocked DocType, also when another app tries to add one at an update.

- A System Manager or a Church Manager can add any DocType to the list or remove one. Add the records of other apps that hold people's data, such as ERPNext's Employee. **Use the Recommended List** adds back what is missing: press it after each update.

- A source on another Churchit DocType saves with an orange warning. Before anyone uses it, set **Roles** on each agent that has that knowledge base, and on its sub-agents.

- While AI is off, Churchit refuses to add a source or change what it reads. A source that already exists keeps its daily copy, whatever the list says: delete sources that you do not need, or untick their **Auto Sync**.

- Add your own manuals and policies as **Text** sources. Add only files and web pages that hold nothing private.

## Ask the manual

Church Office can answer a how-to question, such as "How do I set up a pathway?", from these manuals, and name the section. For this, Churchit adds the manuals to Flow as a knowledge base called **Churchit Manual**, with one source for each section. The manuals hold no church records.

Churchit adds them only while AI is on, on a site with Flow, and when **Embedding Model** in Flow Knowledge Settings names an enabled model (set its Privacy Label first). It adds them after each update and when AI is turned on. If you set the embedding model after you turned on AI, the manuals come at the next update, or when you turn AI off and on again. The AI Access panel says **Added**, **Not added yet** or **Needs an embedding model**.

## Run the Flow server

Flow needs one more program, the **Flow server**, which sends Flow's messages to the AI model. It uses about 250 MB of memory when idle.

- **Docker**: the Churchit Docker setup can start it in its own container. It is off by default, and the default image (Frappe 16) has no Flow, so build an image on a Frappe version with Flow and set IMAGE and TAG in the .env file. Add COMPOSE_PROFILES=flow to the same file and run docker compose up -d.

Check it with docker compose exec backend bench flow-server status. The self-hosting guide in the Churchit repository has more. A model on the same machine, such as Ollama, must listen on an address that the container can reach: localhost inside the container means the container itself.

- **Frappe Cloud**: we could not confirm on November 6, 2026 that Frappe Cloud runs the Flow server. Ask Frappe Cloud support before you plan to use Flow there.

## What no switch stops

Be clear about these limits:

- A person with an API key, an OAuth token or a signed-in session can read and write through the REST API and Frappe's command line tool, whether AI is on or not. While AI is off, also untick **Enable Dynamic Client Registration** in **OAuth Settings**, so that no new app can register itself.

- Administrator has every right. Never connect an AI app as Administrator.

- A person can copy and paste church data into any AI tool. Only your church's policy stops this.

- A browser extension or assistant reads the pages that a person opens, and a Webhook or Server Script can send data to an AI service. Churchit cannot see these.

- On a site with Flow, the daily copy of a knowledge source that already reads church records (see [Flow knowledge](#flow-knowledge)).

- AI in other apps on the same site (see below).

## Other AI on the same site

AI Settings does not control these apps. For each that you have:

- **Frappe Builder**: its AI agent can read private Person fields, because one of its tools skips permissions. On a church site, disable every Builder AI Provider and clear the key in Builder Settings until Builder fixes this.

- **Frappe Assistant Core**: not supported. It runs a second MCP server that Churchit does not stop. Uninstall it, or turn it off for every user.

- **Raven AI**: keep it off (see [Staff Chat](../communications/staff-chat.md) in the Communications manual).

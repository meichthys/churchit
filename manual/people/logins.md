---
title: Logins
emoji: 🔑
sidebar_position: 2
---
Members and staff sign in with a login (a user). A member's login opens the member portal, where they see their own household. A staff login opens the desk, where they do their work.

## Invite a member to the member portal

1. Make sure that the person has a primary email address.
2. Open the person and click **Actions**, then **Invite to Portal**.

Churchit makes a login with the Church User role, links it to the person, and emails them an invitation. If a login with that email already exists, Churchit links it instead, unless another person already has that login or it belongs to a church you cannot see. The button shows only to users who can change the person, and only while the person has an email and no login. It needs an outgoing email account.

Churchit also links a login to a person by itself at the first sign-in, when one person has the same primary email and no login (see Portal accounts under Member Portal).

A visitor who is not signed in sees on the portal: "Part of the church but no login yet? Ask the church office to invite you."

## Staff logins

Staff and volunteers who work in the desk need a user with a **Role Profile** that fits their job:

- **Church Staff**: looks up people, events, groups and ministries, reads published meeting minutes, and keeps their own prayer requests, sign-ups and room bookings.

- **Church Office**: also adds and changes people, families, groups and member transfers (the Church People Editor role).

- **Church Care Team**: also handles care, counseling, visits, background checks, and prayer and alms requests (the Church Pastoral Care role).

- **Church Treasurer**: also handles collections, expenses, funds, budgets and giving statements (the Church Finance role).

- **Church Check-In Volunteer**: uses the [Check-In Station](/desk/check-in) only.

- **Church Follow-up Team**: works on follow-up cards only.

- **Church Branch Manager**: everything in one branch church, but not the website and the shared reports and dashboards.

- **Church Manager**: everything, including settings.

To give someone several jobs, add more than one Role Profile to their user. After they sign in, each person opens the page for their work: a check-in volunteer opens the Check-In Station, a follow-up volunteer opens Follow-up Cards, and other staff open Summary. Linking a staff login to a Person does not change which churches the staff member sees (see the Foundations manual).

## Two-factor authentication

Two-factor authentication asks for a code as well as the password at login, so a stolen password alone does not open the church's records. We recommend it for every staff login, because staff can see personal and medical details.

1. Open [System Settings](/desk/system-settings) and go to the **Login** tab.
2. Under Two Factor Authentication, tick **Enable Two Factor Auth**.
3. Choose the method: **OTP App** (a code from an app such as Google Authenticator), **SMS** (set up SMS Settings first) or **Email**.
4. Save. Each user sets it up the next time they log in.

This asks everyone for a code, members too. To ask only staff, open the [All](/desk/role/All) role and untick **Two Factor Authentication**, then tick it on the Church Staff, Church Manager, Church Check-In and Church Follow-up roles.

## Single sign-on

With single sign-on, people use one account for Churchit and other apps. A System Manager sets it up.

**Sign in to Churchit with another account**, such as Google, Keycloak or Authentik:

1. Open [Social Login Key](/desk/social-login-key/new) and choose the **Social Login Provider**: Google, Keycloak, or Custom for Authentik and other OpenID Connect providers.

2. Type the **Client ID** and **Client Secret** that the other system gives you. For Keycloak, type the realm's address in **Base URL**. For Custom, type a one-word **Provider Name**, such as authentik, the **Authorize URL**, **Access Token URL** and **API Endpoint**, and set **Redirect URL** to /api/method/frappe.integrations.oauth2_logins.custom/authentik.

3. Set **Sign ups** to Deny, so only people who already have a login can sign in. Churchit finds the login by the email address.

4. Tick **Enable Social Login** and save. In the other system, set the redirect address to your site address followed by the Redirect URL.

**Use Churchit logins in another app**, such as a wiki or Nextcloud:

1. Open [OAuth Client](/desk/oauth-client/new) and type the **App Name**.

2. Set **Scopes** to openid, and type the app's redirect address in **Redirect URIs** and **Default Redirect URI**.

3. In **Allowed Roles**, add the roles that can use the app, for example Church Staff, Church Manager, Church Check-In and Church Follow-up for all staff. If you leave it empty, every desk login can use the app.

4. Set **Token Endpoint Auth Method** to Client Secret Post and save.

5. In the app, type the Client ID, the Client Secret and the address: your site address followed by /.well-known/openid-configuration.

If no other app needs to add itself, untick **Enable Dynamic Client Registration** in [OAuth Settings](/desk/oauth-settings).

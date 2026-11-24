---
title: Function Check-Ins
emoji: ✅
sidebar_position: 7
---
A [Function Check-In](/desk/function-check-in) records that a person arrived at a function. Check-ins keep children safe: each child gets a name tag with a security code, the adult who brings them gets a matching pickup tag, and a volunteer releases the child only to someone with the right code. Check-ins also fill in the attendance of the function.

There are four ways to check in:

- **The Check-In Station**: a volunteer at the door finds families by name or phone and checks them in. This is the main way.

- **The self check-in kiosk**: families check themselves in on a tablet at the door.

- **Pre check-in**: a member chooses who comes in the member portal before they leave home, and shows a code at the door.

- **By hand**: staff add a Function Check-In in the desk, or tick people in the Person list and click **Actions**, then **Check In**. These give no security code, so use the station for children who need a pickup tag.

**Example:** The church has ticked **Print Security Codes** in Check-In Settings. On Sunday at 9:45, the Smith family arrives at the children's wing. The volunteer types "Smith" at the Check-In Station, taps the two children and clicks Check In.

Two name tags print with the code K7M2, and a pickup tag with the same code prints for the father. After the service, the father shows his pickup tag. The volunteer clicks Verify Pickup, types K7M2, sees both children and the people allowed to collect them, and releases the children.

Each check-in has a **Kind**: **Regular**, **Guest** (a visitor added at the station) or **Volunteer** (a person who serves). A Volunteer check-in gets no security code, is not counted in the room capacity, and does not start a follow-up card for a first visit. Every kind sets the person's attendance row to Checked-In. A person can be checked in only once to a function.

## Check-In Station

The [Check-In Station](/desk/check-in) is the quickest way to check people in as they arrive. Open it from the sidebar, or from **Actions**, then **Check-In Station**, on a Function. Church Check-In volunteers use it.

1. Choose the **Function** at the top. The station opens on the function last used on that computer when it is today, or else on the next function from today. When you check people in to a function on another day, the station asks you first.

2. Type part of a name, a nickname, a family name or a phone number. The results are grouped by family, so you check parents and children in together. People who have died are not listed.

3. Tap the people who arrived (or **Select all** for a family) and click **Check In**. Press Enter to check in a single match at once.

Untick **Print name tags** to check people in without printing.

Each person in the results shows their age, their grade and, in red, their allergies. A stethoscope icon means that the person has medical notes or an emergency contact: tap it to read them. Only Church Check-In, Church People Editor and Church Manager users see it.

**Scan Card.** A person can show their Member QR Card (see the People manual) or a pre check-in pass instead of saying their name. Click **Scan Card** and hold it in front of the camera. The camera works only when your site uses https.

## New visitors

Click **New Visitor**, or **Add them as a new visitor** when a search finds no one. Confirm the name and the phone number, and click **Add & Check In**.

- The station first looks for people who are already in Churchit with the same name, or a similar name and the same phone number. If it finds someone, click **Check In** next to the right person: nobody new is added. Otherwise click **Add as New Visitor**.

- The new person gets the Membership **Visitor** and the Source **Check-In**, so the member directory does not list them. They are checked in as a Guest.

- Type the **Birth Date** of a visiting child. For a child who comes without an adult in Churchit, open **Emergency Contact** and type a name and phone number.

## The Checked In list

The list on the right shows everyone checked in to the function, newest first, with their photo. It updates every 10 seconds, so you also see the check-ins of other stations. Type part of a name or a security code in **Filter by name or code** to find a person. The buttons on each row:

- **Reprint** the name tag.

- **Undo** the check-in.

- **Check out**: for a person without a pickup tag, such as an adult or a volunteer, who left. A child with a pickup tag leaves only through Verify Pickup.

- **Page parents** (the bell): sends a short message to each Adult of the child's household. An Adult who said yes to texts for Child Safety gets a text, and the others get an email. An Adult that a Pickup Restriction names for the child gets nothing. The station shows the names of the parents it reached. If it shows **No parent reached**, send a runner to find them. You can page the parents of one child once every 2 minutes.

After a person is checked out or collected, only the reprint button stays, and the check-in cannot be undone or deleted. Undoing or deleting a check-in removes the Checked-In row from the function's attendance.

Paging by text needs a gateway in [SMS Settings](/desk/sms-settings) with the Church Check-In role in its Allowed Roles. Otherwise the station sends emails only.

## Headcount

Some people in a room do not check in by name. To count them, type the number of people in the room in the **Headcount** box under Checked In and click **Save**. The attendance total of the function is the larger of the headcount and the number of people counted by name. The box shows only once the function has started.

**Example:** The youth room has 23 teenagers, but only 15 checked in. The leader types 23 in Headcount. The function's attendance total is 23.

## Team

The **Team** tab lists the people who accepted a ministry team position at the function. Click **Check In** next to a name to check that person in as a Volunteer. Their name tag shows the word Volunteer and their position.

## Age and grade limits

In the **Who Can Check In** section on the Attendance tab of a Function, set **Minimum Age**, **Maximum Age**, **Minimum Grade** and **Maximum Grade**. The limits use the age and grade of the person on the day of the function. A person with no birth date (or no graduation year) does not pass an age (or grade) limit.

At the station, a person outside a limit shows a window with the reason: click **Yes** to check them in anyway, or **No**. The station checks a new visitor against the limits too. The kiosk and pre check-in do not offer the function to them. Volunteers have no limit check.

A recurring function gives its limits to each occurrence. You cannot check in to the template of a recurring function: the station shows only its dates.

## Room capacity

The capacity of a function is the total **Capacity** of the rooms in its approved room bookings. With no approved booking, or rooms with no capacity, there is no limit. The people in the room are those who are checked in and not collected or checked out. Volunteers are not counted. Set **Room Capacity** in [Check-In Settings](/desk/check-in-settings):

- **Off**: no capacity check.

- **Warn** (at first): the check-in is saved, and the station shows an orange warning when the room is over capacity.

- **Block**: the station, the kiosk, pre check-in and the Function Check-In form refuse a check-in when the room is full. A place opens again when a child is collected.

## Verify Pickup

Use Verify Pickup when an adult comes to collect a child. It works only when **Print Security Codes** is ticked in [Check-In Settings](/desk/check-in-settings). A household keeps one code for the whole day, also for a child checked in later or at another function. No two households have the same code on one day.

1. Click **Verify Pickup** at the top of the Check-In Station.

2. Type the 4 characters of the code on the adult's pickup tag and press Enter, or click **Scan** and hold the tag's QR code in front of the camera.

3. The station shows each child checked in with this code today, with their photo and function. Below them, it shows who may collect them: the Adults of the household and the family's Authorized Pickups, with their photos. In red, it shows the Pickup Restrictions: who may not collect which child, and what to do.

4. Compare the adult at the desk with these people. Release the child only to one of them.

5. Keep a tick beside each child the adult is taking, and click **Release** beside the adult. Churchit records on each child's check-in who collected them, when, and which volunteer released them.

**Good to know**

- The station refuses to release a child to a restricted person. Only a Church Manager can override this, and must give a reason, which Churchit records with the manager's name.

- If the station shows **No child is checked in with this code today**, do not release the child. Ask a member of staff. A code from an earlier day does not work. If the station shows two families, ask for the child's name.

- In the Function Check-In list, pills show **Awaiting Pickup**, **Picked Up** and **Checked Out**. Add the Collected By and Collected At columns to see who collected each child and when.

- Authorized Pickups and Pickup Restrictions are kept on the Family (see the People manual).

- With more than one church, the station finds only the check-ins of your church's functions and of shared functions.

## Name tags

A name tag prints for every check-in at the station. You can also print tags from a Function Check-In (**Print Name Tag**), from the Function Check-In list, or for any people from the [Person](/desk/person) list (**Actions**, then **Print Name Tags**).

In [Check-In Settings](/desk/check-in-settings):

- **Print Security Codes**: for children's ministry. Everyone in one household gets the same code on their tag for the day, and an extra **Pickup** tag with their names and the code prints for the adult who collects them.

- **Print Allergies on Name Tags**: prints a person's allergies, from the Allergies field of the Person, under their name. Pickup tags never show allergies.

- **Tag Formats by Kind**: a different tag for Regular, Guest or Volunteer check-ins. New sites start with a Volunteer row that prints the word Volunteer and the position.

Name tags print the person's Nickname, or their first name when they have none. Tags are print formats: **Name Tag** for the browser and **Zebra Name Tag** for Zebra printers. To change the layout, duplicate the format, edit the copy and choose it in Check-In Settings.

## Label printer setup

Choose how tags reach the printer under **Name Tag Printing** in [Check-In Settings](/desk/check-in-settings), set the label size (4 × 2 in is the common Zebra name tag, 2.25 × 1.25 in the common Dymo one), and click **Print Test Tag**:

- **Browser**: works with any printer that has a driver (Zebra, Dymo, Brother or an office printer). The print window opens for each batch. On a check-in computer, start Chrome with the --kiosk-printing option and make the label printer the default printer to skip the window.

- **Zebra Browser Print**: silent printing to a Zebra printer connected to the station computer. Install Zebra's free Browser Print app on that computer, make the printer its default, and allow this site when it asks. Set **Printer DPI** to match the printer (203 or 300).

- **QZ Tray**: silent printing to any printer that the station computer can see. Install the free QZ Tray app and, if needed, type the **Printer Name**.

- **Network Printer**: no software on the station computer. Type the IP address of a Zebra printer on the same network as the Churchit server. This needs a server on the church network.

With more than one church, add a row under **Printers Per Church** for each church that prints to its own printer. Fill in only what differs. A station always prints to the printer of its user's church.

## Self check-in kiosk

A self check-in kiosk lets families check themselves in on a tablet or a computer at the door. It shows only today's functions whose [Function Type](/desk/function-type) has **Allow Self Check-In** ticked, from a time before the start (**Self Check-In Opens (Minutes Before Start)** in Check-In Settings, 60 at first) until the end.

To set up a kiosk:

1. Add a [User](/desk/user/new) for the kiosk device, with the role **Church Check-In Kiosk** and no other role. With more than one church, give it exactly one Church User Permission, for the church it serves. In **Restrict IP**, type the address of your church network, so that the login works only at church.

2. Tick **Allow Self Check-In** on each Function Type that families may check in to by themselves.

3. On the kiosk device, open [/check-in-kiosk](/check-in-kiosk), sign in as the kiosk user and leave the page open.

A family types its whole phone number: part of a number finds nobody. A person who is already checked in shows grey and cannot be ticked again. The kiosk shows the people of that household who may check in now, with their photo and grade.

The family ticks who comes, picks a function when there is more than one, and taps **Check In**. The tags print through the printer settings of the kiosk's church. When the household already has a pickup code today, the kiosk prints the name tags without a new pickup tag: use the earlier one.

The kiosk cannot add visitors, check people out or open any record. Children leave through Verify Pickup at the Check-In Station. QZ Tray does not work on the kiosk page.

## Pre check-in

Members can check in before they arrive. When a function of their church allows self check-in and check-in is open, a member opens **Check-in** in the member portal, ticks the people who come, picks the function and taps **Show our pass**. The pass holds a code. At the church, scan it: at the station with **Scan Card**, or at a kiosk with a handheld scanner. The people are checked in and their tags print.

- A member can choose only themselves and the children they may edit. To let an Adult also choose the other adults of the household, tick **Adults may pre check in other adults in their household** in Check-In Settings.

- The code works only until the function ends, and only while check-in is open. A second scan checks in nobody new.

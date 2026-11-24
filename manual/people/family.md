---
title: Family
emoji: 👨‍👩‍👧‍👦
sidebar_position: 3
---
A [Family](/desk/family) is one household: the people who live together, such as parents and their children. The family holds the household's address, its photo, the role of each person in it, and who may collect its children after check-in. A person can be in one household only.

**Example:** The Smith family has John (the primary contact), his wife Mary, their two children, and John's mother Ruth, who lives with them. John and Mary are Adults, the children are Children, and Ruth is an Other Adult: she lives there but is not a parent. Mary's sister Anne may collect the children on Sundays, so she is an Authorized Pickup.

## Add a family

1. Open [Families](/desk/family) and click **Add Family**.
2. Add the people in **Family Members**, with each one's **Relationship to Primary Contact**, such as Wife or Son. You can also pick the Family on each Person form.
3. Set the **Primary Contact**, the person the family is named after, such as Smith - John.
4. Add the **Home Address**, and tick **Mailing** on the address that gets mail. Shared phone numbers and emails go in **Household Phone and Email**.
5. Save.

**Good to know**

- To move a person from another household, remove them from that family first, or change Family on their Person form.

- The primary contact and their spouse are labelled Husband and Wife from the Spouse field of the Person. A member's spouse with no relationship gets one from the member, such as Daughter-in-law for a son's wife.

- When you change the Primary Contact, the family is renamed, and each relationship changes to the relationship to the new primary contact. A relationship that Churchit cannot work out is cleared, and a message names the members to set by hand.

- With more than one church, a family belongs to the church of its Primary Contact.

## Household roles

Each member of a family has a **Household Role**:

- **Adult**: a responsible adult of the household, such as a parent. Adults may edit the household in the member portal and always collect its children.

- **Other Adult**: an adult who lives there but has no authority over the children, such as a grandparent, a grown son or a lodger.

- **Child**: a dependent.

When you save a family with a Primary Contact, Churchit fills in each blank role:
- The primary contact and their spouse are Adults.
- A son, daughter, stepchild or grandchild under the Adult Age is a Child.
- Any other member at or above the Adult Age is an Other Adult.

If Churchit cannot tell, for example for a nephew under 18 or a member with no birth date, it leaves the role blank: set it by hand. Churchit never changes a role that someone set. If you link a spouse after the family has a Primary Contact, check the spouse's role: Churchit may have set Other Adult, so set Adult by hand. The role also sets the person's Life Stage.

A letter or mailing label can address a family by its Adults, for example "John & Jane Smith", or "John Smith & Jane Doe" when their last names differ. A nickname replaces the first name, people who have died are left out, and a family with no Adult is addressed by its family name. When the primary contact leaves the family, the family has no primary contact until you set a new one. In a print format, write {{ salutation(doc.family) }}.

## Merge two families

When one household has two Family records, open the one that you do not want to keep, click **...**, then **Merge Into...**, choose the family to keep and click **Merge**. The members, emails, phones, addresses and Authorized Pickups move to the kept family, without repeats. The kept family keeps its name and Primary Contact.

A kept family with no Primary Contact takes the one of the removed family, and each Household Role stays. A member who came from a family with another primary contact loses their relationship: set it again. Only users who can delete families can merge them. You cannot undo a merge.

## Authorized Pickups

The Adults of a household may always collect its children after check-in. To let another person collect them, such as a grandparent, an aunt or a neighbor, open the family and click **+** next to **Authorized Pickup** in Connections (or open [Authorized Pickups](/desk/authorized-pickup) in the Care folder). Set the **Person**, the **Relationship** and any **Notes**, such as "Sundays only". The person must have a Person record. An Other Adult of the household can be one.

Adults already collect, so only an Other Adult or someone outside the household can be added, once for each family. Deleting a family deletes its Authorized Pickups. Verify Pickup at the Check-In Station shows these people with their photos (see the Ministries manual). Only Church Manager and Church People Editor users of the family's church can open Authorized Pickups. Do not write custody details in the notes: use a Pickup Restriction.

## Pickup Restrictions

A [Pickup Restriction](/desk/pickup-restriction) names someone who may not collect a child, for example because of a court order. It applies also to an Adult of the child's household.

1. Pick the **Child**.
2. Pick the **Restricted Person**, or type their name in **Restricted Name** when they have no Person record.
3. In **What the Volunteer Sees**, write what the check-in volunteer must know, such as how to recognize the person and whom to call.
4. Set **Valid Until** to the last day, or leave it empty.
5. Write the **Reason** and attach the **Court Order** as a private file.

Only Church Manager and Church People Editor users can open a Pickup Restriction. At Verify Pickup, the station shows the restricted person, the child, What the Volunteer Sees and the last day, but never the reason or the court order. It refuses to release the child to that person, and only a Church Manager can override it, with a reason that Churchit records. A page to the parents does not go to the restricted person. The list shows **Active** or **Ended** for each restriction.

**Example:** A court order says that a child's father may not collect her. The office adds a Pickup Restriction with the father as Restricted Person and "Call Pastor Tom at once" in What the Volunteer Sees. If the father comes with the pickup tag, the station shows the warning in red and does not let the volunteer release the child.

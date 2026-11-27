# User accounts and permissions

What an account may do depends on three things:

- its flags: `is_staff`, `is_superuser`, `is_stock_manager` and `is_public_user`;
- its groups;
- its lab memberships.

Six kinds of account cover what labs need; one account can be more than one kind. A stock manager, for example, is usually also in the Husbandry group.

The admin interface and the REST API apply the same rules, which are in `alyx/permissions.py`. The one difference is that only accounts with staff status can sign in to the admin interface.

| | Admin interface | Add | Change | Delete |
| --- | --- | --- | --- | --- |
| [Lab member](#lab-member) | Yes | Most tables | Their own subjects and the records about them | A few tables, and their own notes |
| [Stock manager](#stock-manager) | Yes | As a lab member | As a lab member, and reassigns responsible users | As a lab member |
| [Husbandry](#husbandry) | Yes | As a lab member | As a lab member, plus the colony records of their labs | As a lab member |
| [Superuser](#superuser) | Yes | Everything | Everything | Everything |
| [Public user](#public-user) | Read only | Nothing | Nothing | Nothing |
| [Pipeline user](#pipeline-user) | No | As a lab member | Any record of its labs | As a lab member |

Every signed-in account can view all data. A public user is the exception: they can't see other accounts.

## Terms

- **Staff:** an account with *Staff status* (`is_staff`) ticked. Only staff can sign in to the admin interface; everyone else uses the REST API.
- **Responsible user:** the user in charge of a subject. Records about a subject, such as its sessions, datasets and weighings, belong to its responsible user.
- **Allowed users:** the users a responsible user shares their subjects with. Each user picks them on their own account page.
- **Record users:** the users named on a record itself, such as a session's users or a note's author. A record belongs to them as well.
- **Lab membership:** a link between an account and a lab, with start and end dates (*Lab admin > Lab memberships* in the admin). An account can be a member of several labs, and a data repository can serve several labs. The Husbandry and Pipeline user permissions apply only to records of the labs an account currently belongs to.
- **Lab manager:** not a kind of account of its own. A lab manager who runs the colony is a stock manager and in the Husbandry group.

## Lab member

The standard account.

A lab member can change records that belong to them:

- subjects they are the responsible user of, and every record about those subjects: sessions, actions, weighings, water administrations, datasets, probe insertions, trajectories and fields of view;
- the subjects of users who have added them to their allowed users;
- sessions and other actions that name them among their users;
- tasks of sessions that name them, or of sessions of their labs;
- notes they wrote, data notices, and their own account.

Records that belong to no subject can be changed only by superusers, unless a kind below says otherwise. These include file records, data repositories, labs, projects and dataset types.

A lab member can add records to every table except projects, dataset types, groups and permissions. Datasets, registered with `/register-file`, they can add to the sessions of their labs, or to sessions they own; replacing a dataset that already exists needs the permission to change it.

A lab member can delete surgeries, water administrations, water restrictions, weighings and subject requests. The responsible user doesn't matter for deleting: they can delete these records for any subject. They can also delete notes, but only the ones they wrote, as with changing notes.

**Setting up.**

1. Create the account with *Staff status* ticked. `manage.py set_user_permissions` no longer ticks it, or *Active*, for you.
2. Run `manage.py set_user_permissions`. It puts every account except public users in the `Lab members` group.
3. Add a lab membership for each of the account's labs.

## Stock manager

The person who looks after a lab's colony. A stock manager can do everything a lab member can, and also:

- hand any subject to another responsible user, from the admin's list of subjects;
- choose from every subject, not only their own, when entering an action.

In addition:

- they receive the email sent for each new subject request;
- new subjects get a stock manager as their responsible user by default;
- the daily report doesn't remind them about subjects without a surgery, since stock subjects don't have one.

Being a stock manager doesn't let them edit other people's subjects. That comes from the [Husbandry](#husbandry) group, which stock managers are usually in as well.

**Setting up.** A superuser ticks `is_stock_manager` in the admin's list of users. Alternatively, add the username to the `STOCK_MANAGERS` setting in `settings_lab.py` and run `manage.py set_user_permissions`.

## Husbandry

People who run a lab's colony. Whoever the responsible user is, members can change these records of their labs:

- subjects, litters and breeding pairs;
- lines, genotype tests and zygosities;
- culls.

A lab that has no lab manager can put all its members in this group, so that everyone can manage the colony.

The colony reference tables, which all labs share, are left to superusers. These are alleles, sequences, strains, sources, species and zygosity rules.

**Setting up.**

1. Run `manage.py set_user_permissions`. It creates the `Husbandry` group, with the permission *Can change colony records of its labs*.
2. Add accounts to the group, either from the group's page or from the *Groups* field of each account.
3. Each member needs a lab membership for every lab whose colony they manage.

This replaces an older rule that applied to any group with "husbandry" in its name, and to every lab.

## Superuser

A superuser can do anything, in the admin interface and through the REST API. That includes:

- managing accounts, groups and permissions;
- deleting any record. Deleting a subject also deletes its sessions, datasets and file records.

Only superusers can call `/sync-file-status`, which checks the files of the whole database.

Keep the number of superusers small. Besides the administrators, superuser suits data-management accounts on secured machines, such as those that patch or delete data on Flatiron or AWS.

**Setting up.** Run `manage.py createsuperuser`. Alternatively, add the username to the `SUPERUSERS` setting in `settings_lab.py` and run `manage.py set_user_permissions`; this is how a deployment sets its default superusers. A superuser can't sign in through single sign-on unless `SSO_ALLOW_SUPERUSER` is on.

## Public user

A read-only account, for example for the public IBL database. A public user can:

- sign in to the admin interface and browse it;
- GET from the REST API.

They can't add, change or delete anything. The only account they can see is their own: other users' account records are hidden, though usernames attached to the data are still shown.

**Setting up.** `manage.py set_public_permissions` creates the `Public users` group, which holds view permissions only. A public account has `is_public_user` ticked and belongs to that group. On a public database, self-registration and single sign-on create such accounts.

## Pipeline user

The account a server runs pipelines with, such as the ibllib and mpci tasks. It has no staff status, so it can't sign in to the admin interface and works through the REST API only.

A pipeline user can:

- add records to the same tables as a lab member, including datasets for the sessions of its labs;
- change any record of its labs, whoever the responsible user is. A record's lab is:
  - the lab of its session, or else of its subject, for sessions, subjects, datasets, probe insertions, trajectories, fields of view and their locations, and tasks;
  - the labs that use the repository, for data repositories, for tasks with no session, and for the file records stored in it. A file record also counts for the lab of its dataset's session;
- change and delete the notes it wrote, because a plotting task replaces its earlier note when it is run again.

It can't change accounts, lab memberships, labs, projects or dataset types. It can delete only what a lab member can delete; deleting datasets and file records is left to superuser accounts.

An account that is a member of several labs can change the records of all of them. This suits a server that processes data for more than one lab.

**Setting up.**

1. Run `manage.py set_pipeline_permissions`. It creates the `Pipeline users` group, with the permission *Can change any record of its labs*.
2. Create the account with *Staff status* unticked and add it to the group. `manage.py set_user_permissions` also puts it in `Lab members`, which gives it the permission to add records.
3. Add a lab membership for each lab whose data it processes.
4. If the server's earlier notes were written by another account, make the pipeline user their author, so that it can replace them.

## Managing permissions

- **Change an account's kind.** Tick its flags, or change its *Groups*, on its page in the admin (*Lab admin > Lab members*). Only superusers can change other people's accounts.
- **Add a group.** Go to *Lab admin > Groups*, add a group and pick its permissions, then add accounts to it.
  - Permissions to add, view or delete a table are applied as they are, in the admin interface and in the REST API.
  - The permission to change a table only lets an account change records that are theirs. To change other records it also needs *Can change colony records of its labs* or *Can change any record of its labs*, or superuser status.
- **Set up the standard groups.** Run `manage.py set_user_permissions`, and `manage.py set_pipeline_permissions` where pipeline users are needed. Both can be run again at any time. They add any standard permission missing from the `Lab members`, `Husbandry` and `Pipeline users` groups, and keep permissions you have added yourself. The exceptions are in `Lab members`: permissions it must not have are removed, such as changing projects and the two lab permissions. Neither command changes an account's staff or active status.

## How a write is checked

- **Add:** the account needs the table's add permission.
- **Change:** the account needs the table's change permission, and then one of the following:
  1. it is a superuser;
  2. a rule for the table allows it. Tables with their own rule are tasks, data notices, water restrictions, notes and accounts;
  3. the record is a colony record of the account's labs, and the account has *Can change colony records of its labs*;
  4. the record is of the account's labs, and the account has *Can change any record of its labs*;
  5. the record belongs to it: the account is its subject's responsible user, one of that user's allowed users, or one of the record's users.
- **Delete:** the account needs the table's delete permission. Who owns the record doesn't matter, except for notes, which only their author can delete.
- **Register files** (`/register-file`): before anything is written,
  - adding datasets needs the add permissions for datasets and file records, and a current membership of the dataset's lab, or else owning its session;
  - replacing datasets that already exist needs the permission to change them;
  - a protected dataset is refused, and the request is all or nothing: if one file is refused, none is registered.

  Registering files never changes who is on the session.

A dataset with no session, such as an aggregate over a subject's sessions, belongs to the record it is attached to: its owners and its lab are that record's. For one attached to a record of no lab, such as a tag, the labs that use the repository the files are on count for adding datasets.

Changes to accounts are always checked. The REST API checks every other write only when `ENFORCE_REST_PERMISSIONS` is on. While it is off, writes that fail are still made and logged as warnings (see [REST write permissions](03_deployment.md#rest-write-permissions)).

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.7.0]

## [3.6.4]

### Fixed

- Sessions and probe insertions `tag` REST filters no longer join the datasets table into the
  main query, which made them 3-174x faster.
- `tag` filter on the fields-of-view REST endpoint. `FOVFilter` had a `filter_tag` method but
  never declared the filter that routes to it, so `/fields-of-view?tag=` was silently ignored.
- `dataset_qc_lte` REST filter returned sessions and insertions once per matching dataset, so the
  rows repeated across the paginated response and the count was the number of (row, dataset)
  pairs: `/sessions?dataset_qc_lte=WARNING` reported 3,234,065 of 94,594 sessions.
- `atlas_name`, `atlas_acronym` and `atlas_id` REST filters returned a session once per insertion
  recording the region, and likewise an imaging stack once per slice.
- The `dataset_types`, `datasets`, `dataset_qc_lte` and `atlas_*` REST filters now count and match
  in a subquery instead of joining and grouping over the full row, making them up to 3.5x faster
  (`/sessions?datasets=` 55 s to 16 s, `/chronic-insertions?atlas_acronym=` 0.7 s to 0.01 s).
  `/insertions?tag=&dataset_qc_lte=` previously timed out, as the two joins multiplied.
- The `datasets` REST filter counted the matching datasets rather than the distinct names on the
  insertions and fields-of-view endpoints, so a row holding two datasets of one requested name
  passed as having two different ones: `/insertions?datasets=` now agrees with `/sessions?datasets=`.
  One name matches several datasets across collections and revisions for 142,624 (session, name)
  and 50,078 (insertion, name) pairs, so this over-returned by ~4x on affected queries.
- A dataset name repeated in a `datasets` REST filter, e.g. `?datasets=obj.attr.npy,obj.attr.npy`,
  returned nothing at all rather than the rows having that dataset.
- The chronic insertions REST list eagerly loaded its nested probe insertions while serialising
  each row, which discarded the prefetched result and cost two queries per chronic insertion:
  `/chronic-insertions` issued 329 queries for 176 rows, and now issues 4 regardless of the number
  of rows (1.7x faster overall, 2.3x less time in the database).
- The projects of a session, and the probe insertions of a chronic insertion, are now serialised in
  a defined order. `Project` has no `Meta.ordering` and insertions of one chronic insertion often
  share a session start time and name, so the database was free to return either in any order.
- The sessions, insertions, fields-of-view and chronic insertions REST lists are now totally
  ordered, so a page is the same from one request to the next. 916 sessions share a start time with
  another and 120 insertions share a session start time and name, and rows tied that way came back
  in a different order each request; `/chronic-insertions` had no ordering at all. The keys are
  now `(-start_time, number, subject, pk)` for sessions and `(-session start_time, name, subject,
  session number, pk)` for insertions and fields of view, the primary key being what makes them
  total: `Session` and `ChronicInsertion` declare no uniqueness, and the insertion constraint is on
  (session, name), which does not separate two sessions sharing a start time.
- `/imaging-stacks` returned a stack once per slice, serving 250 rows covering 162 of the 174
  stacks while reporting 174, as the list was ordered by `slices__name` and so joined the slices
  into the query. The stacks are ordered by their own fields now and the slices within each stack
  by the prefetch.
- Admin no longer fails to start with djangorestframework >= 3.18

### Added

- `dataset_qc_lte` filter on the fields-of-view REST endpoint, matching the sessions and probe
  insertions endpoints. The `datasets` filter there now applies the QC bound too, as it does on
  those endpoints, rather than ignoring it.
- Index on `data_dataset.name`, which the `?datasets=` REST filters look up and which had no index
  (23 MB; deduplicated, as a few hundred names repeat across the table). Built concurrently, as
  the table is continuously written. `/insertions?datasets=` is 7x faster, but note
  `/sessions?datasets=` with two or more names is ~1.3x slower, as the planner switches from a
  parallel sequential scan to a bitmap scan past roughly 5% of the table.
- A single dataset name in the sessions `datasets` REST filter is now matched with one Exists
  semi-join anchored on the session, rather than gathering every dataset of that name in the table
  to group them: `/sessions?datasets=` with one name is 1.8x faster (9.9 s to 5.4 s), and 8x faster
  than before this release. Several names, or a `dataset_qc_lte` below WARNING, keep the grouped
  count, both being cases where the semi-join measured no better or worse. The insertions and
  fields-of-view filters are not special-cased, measuring the same either way.

### Changed
- The custom admin site is now installed through `alyx.apps.AlyxAdminConfig` instead of by
  reassigning `django.contrib.admin.site`. **Deployments must replace `'django.contrib.admin'`
  with `'alyx.apps.AlyxAdminConfig'` in their `INSTALLED_APPS`**, otherwise the stock Django
  admin index is served in place of the Alyx one. `alyx.base.mysite` is gone; use
  `django.contrib.admin.site`, which now refers to the site Alyx serves.
- Groups are administered through `django.contrib.auth`'s `GroupAdmin` rather than a bare
  `ModelAdmin`, so group permissions get the two-pane selector

## [3.6.3]

### Fixed

- No longer required to quote special characters in database connection settings

## [3.6.2]

### Fixed

- Scoped delete_zygosity_rule post delete hook, improving performance on delete

### Changed

- Removed unused dj_database_url dependency
- Omit WSGI from CI code coverage
- Changed default docker project name
- Use commit message for release description on squash commits to master
- Pin ruff and remove flake8

### Added

- DOI badge in README
- Release steps to README

## [3.6.1]

### Fixed

- Correct relative paths from aggregate datasets with revisions, registered via REST
- Added missing migration file

### Changed

- Workflow tests now run in parallel and asserts no new migrations

## [3.6.0]

### Added

- `DataNotice` model to attach information/notices to datasets (#1007)
- Registered-file validation (#1014)
- CI/CD release pipeline: bumping `__version__` on `master` cuts a git tag + GitHub release
  and builds/pushes the `alyx_apache[_base]` docker images, gated behind an ansible smoke test (#954)

### Changed

- The production docker image and compose are now built from this repository (`deploy/app/`) as
  the single source of truth; `iblalyx` is no longer baked into the image (bind-mounted at deploy
  time), and deploy orchestration (ansible, per-server overrides) lives in `iblsre` (#1017)
- Restructured `deploy/` into `app/` (production) and `editable/` (postgres-only for editable installs)
- Bump Django 5.2.14 → 5.2.15 (#1012) and Pillow 12.2.0 → 12.3.0 (#1019)

### Fixed

- Remove unknown dataset type from the test dump fixture (#1021)
- Flaky task-cleanup test (save within the datetime mock context)

## [3.5.1]

### Fixed

- to be culled filter in cull subjects admin

## [3.5.0]

### Modified

- support registration of datasets unassociated to a session
- sort insertions by name
- use ONE Globus class for transfers

### Added

- user REST request rate limits

## [3.4.2]

### Fixed
- error in register-files endpoint when labs is a list

## [3.4.1]

### Modified
- added actual severity column to SubjectCullAdmin
- renamed 'Mice' to 'Subject' in views

### Fixed
- all alive filters depend on death date instead of cull
- django 5.1 deprecation: CheckConstraint check -> condition
- various filter typos, e.g. 'To be reduced' filter now works
- improvements to notifications performance
- fix log typo in delete_expired_notifications management command

## [3.4.0]

### Modified
- moved prune_cortexlab.py to iblalyx repository

### Fixed
- removed test for removed subject death save logic
- fixed command for dumping test database fixtures

### Added
- in `alyx.misc` the one_cache command module contains utils to generate cache dataframes from sessions and datasets querysets

## [3.3.3] 2025-12-04

### Fixed
- default implant weight is 0 and not none to allow plotting of water curves.
- water restriction admin form makes sure the current subject is selectable even if it is not alive anymore.

## [3.3.2] 2025-11-26

### Fixed
- water history plots: the weight thresholds is `(w - iw) / (ew - iw)`, where `w` is the measured weight, `iw` the implant weight and `ew` the expected weight.  Expected weight is `(ew = (rw * a + zw *b) + iw`  (weighted sum of reference weight and zscore weight + implant weight).  The display was computing thresholds according to `w/ew` , not taking into account the implant weight and is now fixed.


## [3.3.1] 2025-11-06

### Changed

- The documentation endpoint `/docs` is only for the browser and uses openapiv3. The database schemes are accessed through `/api/schema`. For compatibility, if the headers require `coreapi`, the endpoint returns a frozen set of endpoint to the client. [#929](https://github.com/cortex-lab/alyx/pull/929)
- narrative template is now available on the base action instead of only for surgeries [#938](https://github.com/cortex-lab/alyx/pull/938)


### Removed

- coreapi dependency is removed
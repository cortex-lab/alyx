# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
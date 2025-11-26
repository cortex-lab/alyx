# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [3.3.2] 2025-11-26

### Fixed

- water history plots: the weight thresholds is `(w - iw) / (ew - iw)`, where `w` is the measured weight, `iw` the implant weight and `ew` the expected weight.  Expected weight is `(ew = (rw * a + zw *b) + iw`  (weighted sum of reference weight and zscore weight + implant weight).  The display was computing thresholds according to `w/ew` , not taking into account the implant weight and is now fixed.


## [3.3.1] 2025-11-06

### Changed

- The documentation endpoint `/docs` is only for the browser and uses openapiv3. The database schemes are accessed through `/api/schema`. For compatibility, if the headers require `coreapi`, the endpoint returns a frozen set of endpoint to the client. [#929](https://github.com/cortex-lab/alyx/pull/929)

- narrative template is now available on the base action instead of only for surgeries [#938](https://github.com/cortex-lab/alyx/pull/938)


### Removed

- coreapi dependency is removed
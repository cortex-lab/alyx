# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added


### Changed

- The documentation endpoint `/docs` is only for the browser and uses openapiv3. The database schemes are accessed through `/api/schema`. For compatibility, if the headers require `coreapi`, the endpoint returns a frozen set of endpoint to the client. [#929](https://github.com/cortex-lab/alyx/pull/929)

- narrative template is now available on the base action instead of only for surgeries [#938](https://github.com/cortex-lab/alyx/pull/938)


### Removed

- coreapi dependency is removed
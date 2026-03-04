# Changelog

## [0.5.0] - 2026-03-04

### 🚀 Features

- Structured vendor extensions metadata with deprecation-related info ([b0942c8](https://github.com/fractalvision/fastapi-deprecation/commit/b0942c83ca175fa464927ab591a19919bba0ef0a))
- Dynamic OpenAPI Integration ([ddad5ff](https://github.com/fractalvision/fastapi-deprecation/commit/ddad5ffd6c252fdbecbbbd845215b0674676ffb5))
- Add dynamic deprecation support for WebSocket and SSE streams ([3a5d1fd](https://github.com/fractalvision/fastapi-deprecation/commit/3a5d1fd3d475fdde89154660b894d04f48cedbbd))
- Implement Universal Deprecation Metrics Tracker ([1b06c68](https://github.com/fractalvision/fastapi-deprecation/commit/1b06c68db289dbee759ed0c4c8a8a7ad649f7d0d))

### 🐛 Bug Fixes

- Probabilistic brownouts logic bypassed if no deprecation date set ([5c06401](https://github.com/fractalvision/fastapi-deprecation/commit/5c06401986085be2803fe0f5444bdf402ec55e7b))
- Singular link missing from the openapi schema extension block ([2bc6f49](https://github.com/fractalvision/fastapi-deprecation/commit/2bc6f494247946c9ecfdf32a2365b22e21c94b8f))
- *(websocket)* Encode accept headers as ASGI compliant byte-tuples ([37f9e1d](https://github.com/fractalvision/fastapi-deprecation/commit/37f9e1d5fb12eb3266c2c71d51056a7e0493b620))

### 🚜 Refactor

- Link to the deprecation info relation type aligned with standards (deprecation/sunset), better engine naming, docstrings with settings hints, alternative status via config ([8e4cbd8](https://github.com/fractalvision/fastapi-deprecation/commit/8e4cbd8fb9583c4574223614693ae1ac667b2a41))

### 📚 Documentation

- Update for clarity ([eeb2d02](https://github.com/fractalvision/fastapi-deprecation/commit/eeb2d02d73726dcd6dac7bdc630b45b29f74c17f))
- Update to reflect changes ([14ba925](https://github.com/fractalvision/fastapi-deprecation/commit/14ba9255d52abfc116ce160652e46d12e0d04906))
- Update documentation for dynamic OpenAPI schema ([9d26954](https://github.com/fractalvision/fastapi-deprecation/commit/9d26954077f02b6a18b595d098d3ef6bb1507455))

### ⚡ Performance

- Optimize stream Engine evaluations with monotonic throttling ([57fdaa7](https://github.com/fractalvision/fastapi-deprecation/commit/57fdaa7e1b2945ac8a2eccc2f2e5dd3da0418573))

### ⚙️ Miscellaneous Tasks

- Demo app updated ([1387314](https://github.com/fractalvision/fastapi-deprecation/commit/1387314a9678561d40afaceea128e19a9601ed5d))
- Added branches condition to workflows ([7557cff](https://github.com/fractalvision/fastapi-deprecation/commit/7557cff262e378bb9ab5cebbe3ddff5dd2a75d11))
- Fixed typo in GH action ([a6d9d66](https://github.com/fractalvision/fastapi-deprecation/commit/a6d9d66fef78c91feb860f8c967cfa2d96278c37))

## [0.4.0] - 2026-02-21

### 🚀 Features

- Dynamic cache tags and chaos engineering brownouts ([1b87a62](https://github.com/fractalvision/fastapi-deprecation/commit/1b87a62b904fd2150d9c00a08e47403b6a31ed74))
- Validate brownout configurations to prevent conflicting states ([c3091c8](https://github.com/fractalvision/fastapi-deprecation/commit/c3091c8114de8099fcfe4e7972a513c0f4452bf9))

### 🚜 Refactor

- Deprecation core logic moved to engine, unify telemetry, openapi fix, docs ([c16feb4](https://github.com/fractalvision/fastapi-deprecation/commit/c16feb4bb1abb8468ffa83d1549a027d7c7e6026))

### ⚙️ Miscellaneous Tasks

- Update CHANGELOG.md for v0.3.0 ([900d815](https://github.com/fractalvision/fastapi-deprecation/commit/900d815a256b5acdd845db421d1c9234fe8e0a11))
- *(release)* Prepare for 0.4.0 ([53bbd97](https://github.com/fractalvision/fastapi-deprecation/commit/53bbd9798caab6e75cba49f79543f57d2d52e9f0))

## [0.3.0] - 2026-02-20

### 🚀 Features

- Implement advanced middleware, custom responses, enhanced links, and caching ([ca21dbe](https://github.com/fractalvision/fastapi-deprecation/commit/ca21dbe5f10e5ac0a44f9b428c1fdba75a4fbc65))

### 📚 Documentation

- Add rate limiting guide and showcase example app ([68721bb](https://github.com/fractalvision/fastapi-deprecation/commit/68721bbcd62bd2772a4f10a31aed52b88683d373))

### ⚙️ Miscellaneous Tasks

- Configure git-cliff for dynamic changelog generation ([383a5e7](https://github.com/fractalvision/fastapi-deprecation/commit/383a5e72fa5fdc54047b4f54ab989f2d5c24c130))

## [0.2.1] - 2026-02-20

### 📚 Documentation

- Update documentation, configuration and license ([581d394](https://github.com/fractalvision/fastapi-deprecation/commit/581d39490f1ff9105bbf40eee8d37f2b5c949194))

### ⚙️ Miscellaneous Tasks

- Add GitHub Actions workflows for testing and publishing ([c9b89b4](https://github.com/fractalvision/fastapi-deprecation/commit/c9b89b49c607f468313017bfa750db2c49dbdbe2))

## [0.2.0] - 2026-02-19

### 🚀 Features

- Recursive OpenAPI deprecation for mounted apps ([688b07a](https://github.com/fractalvision/fastapi-deprecation/commit/688b07a3bd82d5e524cd456e113d0718bd3d0a34))

## [0.1.0] - 2026-02-19

### 🚀 Features

- Initial commit of fastapi-deprecation library ([c980991](https://github.com/fractalvision/fastapi-deprecation/commit/c9809915e39bd518f20c5e427aa2cf30aa926399))

<!-- generated by git-cliff -->

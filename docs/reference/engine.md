# Engine

The `engine` module serves as the functional core of the `fastapi-deprecation` package. It contains the primary configuration model (`DeprecationConfig`) and the agnostic evaluation logic (`evaluate_deprecation`) used by both decorators and middlewares.

## DeprecationConfig

`DeprecationConfig` is the universal data structure that holds all metadata for a deprecation lifecycle. Whether you define your deprecations via the `@deprecated` decorator or the `DeprecationMiddleware`, they are all internally normalized into `DeprecationConfig` definitions.

It also contains the centralized telemetry dispatch mechanisms unifying logging events across the framework.

::: fastapi_deprecation.engine
    options:
        members:
            - DeprecationConfig
            - ActionType
            - DeprecationResult
            - set_deprecation_callback
            - evaluate_deprecation

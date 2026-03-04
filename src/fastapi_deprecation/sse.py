import json
import time
from typing import AsyncGenerator, Iterator

from .engine import DeprecationConfig, process_deprecation, ActionType
from datetime import datetime, timezone


async def deprecated_sse_generator(
    generator: AsyncGenerator[str, None] | Iterator[str],
    config: DeprecationConfig,
) -> AsyncGenerator[str, None]:
    """
    Wraps an SSE generator to gracefully inject a deprecation/sunset
    event into the stream if the sunset date is reached during the stream.
    """

    # We yield items from the underlying generator until it finishes or sunset is reached
    is_async = hasattr(generator, "__anext__")
    last_check_time = 0.0

    try:
        while True:
            # Throttle processing to at most once per second for high-throughput streams
            current_time = time.monotonic()
            if current_time - last_check_time >= 1.0:
                now = datetime.now(timezone.utc)
                result = process_deprecation(config, now)
                last_check_time = current_time

                if result.action == ActionType.BLOCK:
                    sunset_msg = "Endpoint has been sunset and connection closed."
                    if config.detail:
                        sunset_msg = config.detail
                    elif config.alternative:
                        sunset_msg = (
                            f"Endpoint sunset. Replaced by {config.alternative}"
                        )

                    data = json.dumps({"detail": sunset_msg})
                    yield f"event: sunset\ndata: {data}\n\n"
                    break

            if is_async:
                item = await generator.__anext__()
            else:
                item = next(generator)

            yield item
    except (StopAsyncIteration, StopIteration):
        pass

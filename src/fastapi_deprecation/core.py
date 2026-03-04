import inspect
import functools
from typing import Optional, Callable
from fastapi import Request, Response, WebSocket, status
from fastapi.concurrency import run_in_threadpool

from .dependencies import DeprecationDependency
from .utils import DateInput


def deprecated(
    deprecation_date: Optional[DateInput] = None,
    sunset_date: Optional[DateInput] = None,
    alternative: Optional[str] = None,
    alternative_status: int = status.HTTP_301_MOVED_PERMANENTLY,
    link: Optional[str] = None,
    links: Optional[dict[str, str]] = None,
    brownouts: Optional[list[tuple[DateInput, DateInput]]] = None,
    detail: Optional[str] = None,
    response: Optional[Callable[[], Response] | Response] = None,
    inject_cache_control: bool = False,
    cache_tag: Optional[str] = None,
    brownout_probability: float = 0.0,
    progressive_brownout: bool = False,
):
    """
    Decorator to mark an endpoint as deprecated.
    In FastAPI, this modifies the function signature to ensure 'request' and 'response' are available,
    then executes the DeprecationDependency logic.

    Args:
        deprecation_date (Optional[DateInput]): The date when the endpoint is deprecated.
        sunset_date (Optional[DateInput]): The date when the endpoint is sunset.
        alternative (Optional[str]): The alternative endpoint to redirect to.
        link (Optional[str]): The link to the deprecation information (policy or migration guide).
        links (Optional[dict[str, str]]): Additional links for deprecation information (newer versions, etc.).
        brownouts (Optional[list[tuple[DateInput, DateInput]]]): List of brownout periods.
        detail (Optional[str]): Additional detail about the deprecation.
        response (Optional[Callable[[], Response] | Response]): Custom response to return.
        inject_cache_control (bool): Whether to inject cache control headers.
        cache_tag (Optional[str]): Cache tag for the deprecation.
        brownout_probability (float): Probability of a brownout.
        progressive_brownout (bool): Whether to use progressive brownout.
    """
    dep = DeprecationDependency(
        deprecation_date=deprecation_date,
        sunset_date=sunset_date,
        alternative=alternative,
        alternative_status=alternative_status,
        link=link,
        links=links,
        brownouts=brownouts,
        detail=detail,
        response=response,
        inject_cache_control=inject_cache_control,
        cache_tag=cache_tag,
        brownout_probability=brownout_probability,
        progressive_brownout=progressive_brownout,
    )

    def decorator(func: Callable):
        sig = inspect.signature(func)
        params = list(sig.parameters.values())

        # Check if request/response already in params
        has_request = any(p.name == "request" for p in params)
        has_response = any(p.name == "response" for p in params)

        has_varkw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params)

        # We need to create a wrapper that accepts request/response if needed
        # But we also need to expose them to FastAPI so it injects them.

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request/response/websocket from kwargs
            req: Request = kwargs.get("request")
            res: Response = kwargs.get("response")
            ws: WebSocket = kwargs.get("websocket")

            if ws:
                from datetime import datetime, timezone
                from .engine import ActionType, process_deprecation
                from .websocket import DeprecatedWebSocket

                now = datetime.now(timezone.utc)
                result = process_deprecation(dep.config, now)

                if result.action == ActionType.BLOCK:
                    wrapper_ws = DeprecatedWebSocket(ws, result, dep.config)
                    await wrapper_ws.handle_block(dep.config)
                    return
                else:
                    # Provide wrapper to handler
                    kwargs["websocket"] = DeprecatedWebSocket(ws, result, dep.config)

                    if not has_varkw and not any(p.name == "websocket" for p in params):
                        kwargs.pop("websocket", None)

                    if inspect.iscoroutinefunction(func):
                        return await func(*args, **kwargs)
                    else:
                        from fastapi.concurrency import run_in_threadpool as run_in_pool

                        return await run_in_pool(func, *args, **kwargs)

            if req and res:
                from .dependencies import DeprecationSunset

                try:
                    await dep(req, res)
                except DeprecationSunset as e:
                    block_res = e.response
                    if getattr(block_res, "media_type", None) == "text/event-stream":
                        from starlette.responses import StreamingResponse

                        if isinstance(block_res, StreamingResponse):
                            from .sse import deprecated_sse_generator

                            block_res.body_iterator = deprecated_sse_generator(
                                block_res.body_iterator, dep.config
                            )
                    return block_res

            # Prepare kwargs for func
            func_kwargs = kwargs.copy()

            # If func did NOT ask for request/response and doesn't accept **kwargs,
            # we must remove them to avoid TypeError.
            if not has_varkw:
                if not has_request:
                    func_kwargs.pop("request", None)
                if not has_response:
                    func_kwargs.pop("response", None)

            if inspect.iscoroutinefunction(func):
                ret_val = await func(*args, **func_kwargs)
            else:
                ret_val = await run_in_threadpool(func, *args, **func_kwargs)

            # If the user returns a Response directly (like StreamingResponse), FastAPI
            # often ignores headers attached to the injected `res` object. We must manually merge them.
            if isinstance(ret_val, Response) and res:
                for k, v in res.headers.items():
                    ret_val.headers.setdefault(k, v)

            # Auto-wrap SSE streams
            if (
                isinstance(ret_val, Response)
                and getattr(ret_val, "media_type", None) == "text/event-stream"
            ):
                from starlette.responses import StreamingResponse

                if isinstance(ret_val, StreamingResponse):
                    from .sse import deprecated_sse_generator

                    ret_val.body_iterator = deprecated_sse_generator(
                        ret_val.body_iterator, dep.config
                    )

            return ret_val

        # Update wrapper signature
        new_params = list(params)  # Start with original params

        args_to_add = []
        if not has_request and not any(p.annotation == WebSocket for p in params):
            args_to_add.append(
                inspect.Parameter(
                    "request",
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    annotation=Request,
                )
            )
        if not has_response and not any(p.annotation == WebSocket for p in params):
            args_to_add.append(
                inspect.Parameter(
                    "response",
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    annotation=Response,
                )
            )

        if args_to_add:
            # Find insertion point: Before VAR_KEYWORD (**kwargs) if present
            insert_idx = len(new_params)
            for i, p in enumerate(new_params):
                if p.kind == inspect.Parameter.VAR_KEYWORD:
                    insert_idx = i
                    break

            # Insert the new arguments
            new_params[insert_idx:insert_idx] = args_to_add

        wrapper.__signature__ = sig.replace(parameters=new_params)

        # Mark the wrapper for OpenAPI integration
        wrapper.__deprecation__ = dep

        return wrapper

    return decorator

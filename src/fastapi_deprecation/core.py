import inspect
import functools
from typing import Optional, Callable
from fastapi import Request, Response, status
from .dependencies import DeprecationDependency
from .utils import DateInput
from fastapi.concurrency import run_in_threadpool


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
            # Extract request/response from kwargs (FastAPI injects them because we ask in signature)
            req: Request = kwargs.get("request")
            res: Response = kwargs.get("response")

            if req and res:
                from .dependencies import DeprecationSunset

                try:
                    await dep(req, res)
                except DeprecationSunset as e:
                    return e.response

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
                return await func(*args, **func_kwargs)
            else:
                return await run_in_threadpool(func, *args, **func_kwargs)

        # Update wrapper signature
        new_params = list(params)  # Start with original params

        args_to_add = []
        if not has_request:
            args_to_add.append(
                inspect.Parameter(
                    "request",
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    annotation=Request,
                )
            )
        if not has_response:
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

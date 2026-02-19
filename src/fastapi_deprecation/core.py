import inspect
import functools
from typing import Optional, Callable
from fastapi import Request, Response
from .dependencies import DeprecationDependency
from .utils import DateInput
from fastapi.concurrency import run_in_threadpool


def deprecated(
    deprecation_date: Optional[DateInput] = None,
    sunset_date: Optional[DateInput] = None,
    alternative: Optional[str] = None,
    link: Optional[str] = None,
    brownouts: Optional[list[tuple[DateInput, DateInput]]] = None,
    detail: Optional[str] = None,
):
    """
    Decorator to mark an endpoint as deprecated.
    In FastAPI, this modifies the function signature to ensure 'request' and 'response' are available,
    then executes the DeprecationDependency logic.
    """
    dep = DeprecationDependency(
        deprecation_date=deprecation_date,
        sunset_date=sunset_date,
        alternative=alternative,
        link=link,
        brownouts=brownouts,
        detail=detail,
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
                await dep(req, res)

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

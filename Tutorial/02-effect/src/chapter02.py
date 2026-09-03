"""A small callable and awaitable Effect for tutorial chapter 02."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable, Iterable
from typing import cast

Cleanup = Callable[[], object]
Setup = Callable[[], object]


async def _run_cleanup(cleanup: Cleanup) -> None:
    result = cleanup()
    if inspect.isawaitable(result):
        await cast(Awaitable[object], result)


class Effect:
    """Run setup now and dispose every produced cleanup exactly once."""

    def __init__(self, setup: Setup) -> None:
        self._cleanups: list[Cleanup] = []
        self._dispose_task: asyncio.Task[None] | None = None
        self._setup_task: asyncio.Task[None] | None = None
        self._setup_complete = asyncio.Event()
        self._setup_error: BaseException | None = None

        try:
            result = setup()
            if callable(result):
                self._cleanups.append(cast(Cleanup, result))
                self._setup_complete.set()
            elif inspect.isawaitable(result):
                self._setup_task = asyncio.create_task(
                    self._finish_async_setup(cast(Awaitable[object], result))
                )
            else:
                self._collect_sync(result)
                self._setup_complete.set()
        except BaseException:
            self._setup_complete.set()
            raise

    @property
    def disposed(self) -> bool:
        return self._dispose_task is not None

    def __await__(self):  # type: ignore[no-untyped-def]
        return self._wait_setup().__await__()

    def __call__(self) -> asyncio.Task[None]:
        if self._dispose_task is None:
            self._dispose_task = asyncio.create_task(self._dispose())
        return self._dispose_task

    async def _wait_setup(self) -> Effect:
        await self._setup_complete.wait()
        if self._setup_error is not None:
            raise self._setup_error
        return self

    def _collect_sync(self, result: object) -> None:
        if result is None:
            return
        if isinstance(result, Iterable) and not isinstance(result, (str, bytes, bytearray)):
            cleanups = list(cast(Iterable[object], result))
            if not all(callable(cleanup) for cleanup in cleanups):
                raise TypeError("Invalid effect")
            self._cleanups.extend(cast(list[Cleanup], cleanups))
            return
        raise TypeError("Invalid effect")

    async def _finish_async_setup(self, result: Awaitable[object]) -> None:
        try:
            resolved = await result
            if callable(resolved):
                self._cleanups.append(cast(Cleanup, resolved))
            else:
                self._collect_sync(resolved)
        except BaseException as error:
            self._setup_error = error
        finally:
            self._setup_complete.set()

    async def _dispose(self) -> None:
        await self._setup_complete.wait()
        errors: list[BaseException] = []
        while self._cleanups:
            try:
                await _run_cleanup(self._cleanups.pop())
            except asyncio.CancelledError:
                raise
            except BaseException as error:
                errors.append(error)
        if self._setup_error is not None:
            raise self._setup_error
        if errors:
            raise BaseExceptionGroup("effect cleanup failed", errors)

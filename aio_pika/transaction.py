import asyncio

from .common import FutureStore
from .exceptions import TransactionClosed


class Transaction:
    def __init__(self, channel, future_store: FutureStore):
        self._channel = channel
        self._future_store = future_store
        self.closing = self._future_store.create_future()

    def _create_future(self, timeout=None):
        if self.closing.done():
            raise RuntimeError("Can't reuse closed transaction")

        return self._future_store.create_future(timeout)

    def select(self, timeout=None):
        future = self._create_future(timeout)
        self._channel.tx_select(future.set_result)
        return future

    def rollback(self, timeout=None):
        future = self._create_future(timeout)
        self._channel.tx_rollback(future.set_result)
        return future

    def commit(self, timeout=None):
        future = self._create_future(timeout)
        self._channel.tx_commit(future.set_result)
        return future

    def close(self, exc: Exception=TransactionClosed):
        if not self.closing.done():
            self.closing.set_result(None)
        self._future_store.reject_all(exc)

    async def __aenter__(self):
        result = await self.select()
        return result

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            await self.rollback()
        else:
            await self.commit()

        self.close()

    def __del__(self):
        self.close(ReferenceError('Transaction deleted'))

    def on_close_callback(self, result: asyncio.Future):
        exc = result.exception()

        if exc:
            self.close(exc)

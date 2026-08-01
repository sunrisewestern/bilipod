import asyncio
import threading

from src.bilipod.executing import scheduler


def test_run_async_uses_bound_service_loop():
    async def exercise():
        scheduler.bind_service_event_loop()
        service_thread_id = threading.get_ident()

        async def identify_thread():
            return threading.get_ident()

        result = {}

        def scheduled_thread():
            result["thread_id"] = scheduler.run_async(identify_thread)

        thread = threading.Thread(target=scheduled_thread)
        thread.start()
        while thread.is_alive():
            await asyncio.sleep(0.01)
        thread.join()

        assert result["thread_id"] == service_thread_id

    asyncio.run(exercise())

import asyncio
import threading

from src.bilipod.executing import update


def test_update_signal_wakes_listener_from_another_thread():
    async def wait_for_signal():
        update.update_event.clear()
        update.bind_update_event_loop()

        trigger_thread = threading.Thread(target=update.notify_update_event)
        trigger_thread.start()
        try:
            await asyncio.wait_for(update.update_event.wait(), timeout=1)
        finally:
            trigger_thread.join()
            update.update_event.clear()

    asyncio.run(wait_for_signal())

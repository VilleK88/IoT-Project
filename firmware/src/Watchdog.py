from machine import WDT
import asyncio

class Watchdog:
    def __init__(self):
        # Start the hardware watchdog.
        # The system will reset if the watchdog is not fed for 30 seconds.
        self._wdt = WDT(timeout=30000)

    async def watchdog_task(self):
        """Periodically feed the watchdog while asyncio is running normally."""

        while True:
            self._wdt.feed()

            # Feed every 5 seconds, leaving plenty of margin before
            # the 30-second watchdog timeout.
            await asyncio.sleep_ms(5000)
from machine import WDT
import machine
import asyncio

class Watchdog:
    def __init__(self, log_manager):
        self._log_manager = log_manager
        self._normal_timeout_ms = 30_000  # 30 seconds.
        self._feed_interval_ms = 5000  # 5 seconds.
        # Start the hardware watchdog.
        self._wdt = WDT(timeout=self._normal_timeout_ms)

    def feed(self):
        self._wdt.feed()

    async def watchdog_task(self):
        while True:
            self._wdt.feed()
            await asyncio.sleep_ms(self._feed_interval_ms)

    def log_boot_reason(self):
        cause = machine.reset_cause()
        if cause == machine.PWRON_RESET:
            self._log_manager.info("System boot: power-on reset")
        elif cause == machine.WDT_RESET:
            self._log_manager.error("System boot: watchdog reset detected")
        elif cause == machine.SOFT_RESET:
            self._log_manager.info("System boot: software reset")
        elif cause == machine.HARD_RESET:
            self._log_manager.warning("System boot: hardware reset")
        elif cause == machine.DEEPSLEEP_RESET:
            self._log_manager.info("System boot: wake from deep sleep")
        else:
            self._log_manager.warning("System boot: unknown reset cause {}".format(cause))

    def feed_interval_ms(self):
        return self._feed_interval_ms
import pytest

from cordis import Context, LogLevel, LogMessage


class MemoryExporter:
    def __init__(self) -> None:
        self.messages: list[LogMessage] = []

    def export(self, message: LogMessage) -> None:
        self.messages.append(message)


@pytest.mark.asyncio
async def test_logger_levels_and_exporter_ownership() -> None:
    context = Context()
    exporter = MemoryExporter()

    def plugin(plugin_context: Context, config: object) -> None:
        plugin_context.exporter(exporter)

    fiber = context.plugin(plugin)
    await fiber.wait()
    context.logger.set_level("agent", LogLevel.WARNING)
    log = context.logger("agent.loop")
    log.info("ignored %s", "message")
    log.error("failed %s", "request")

    assert [message.text for message in exporter.messages] == ["failed request"]
    await fiber.dispose()
    log.error("after disposal")
    assert len(exporter.messages) == 1
    await context.aclose()

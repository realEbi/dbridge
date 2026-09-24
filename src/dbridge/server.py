import asyncio

from dbridge.core.engine import Engine
from dbridge.protocol.handlers import Dispatcher
from dbridge.protocol.transport.stdio import StdioTransport


def main() -> None:
    engine = Engine()
    dispatcher = Dispatcher(engine)
    asyncio.run(StdioTransport().serve(dispatcher))


if __name__ == "__main__":
    main()

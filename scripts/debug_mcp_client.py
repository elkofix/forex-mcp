import asyncio
import sys
import traceback

sys.path.append("agent")
from agent.graph import MCPStdioClient


async def main() -> None:
    client = MCPStdioClient(
        command="mcp_massive",
        args=[],
        env={
            "POLYGON_API_KEY": "test_key",
            "MASSIVE_API_KEY": "test_key",
        },
    )

    try:
        await client.start()
        tools = await client.list_tools()
        print(f"tools={len(tools)}")
        if tools:
            print(f"first_tool={tools[0].get('name')}")
    except Exception as exc:
        print(f"ERR {type(exc).__name__}: {exc}")
        traceback.print_exc()
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())

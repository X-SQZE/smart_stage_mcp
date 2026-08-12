import asyncio
from mon_serveur import mcp

async def dump_tools():
    tools = await mcp.list_tools()
    for t in tools:
        print(f"=== {t.name} ===")
        print("Description:", t.description)
        print("Schema:", t.inputSchema)
        print()

asyncio.run(dump_tools())
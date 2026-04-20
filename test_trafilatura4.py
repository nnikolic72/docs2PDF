import asyncio

import httpx
import trafilatura


async def main():
    async with httpx.AsyncClient() as client:
        r = await client.get("https://textual.textualize.io/")
        html = r.text
        content = trafilatura.extract(html, include_links=True, include_formatting=True, output_format="html")
        print(content[:500])


asyncio.run(main())

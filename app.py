import asyncio
import os
from aiohttp import web

# ---------------------------------------------------------------- Web Server for Render
async def handle(request):
    return web.Response(text="Bot web service is live & active!")

async def start_web_server():
    server = web.Application()
    server.add_routes([web.get("/", handle)])
    runner = web.AppRunner(server)
    await runner.setup()
    
    # Render automatic PORT assignment
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Web server started successfully on port {port}")

# ---------------------------------------------------------------- Main Entry Point
async def main():
    # 1. Start the web server
    await start_web_server()
    
    # 2. Import your original bot Client instance and start it
    from bot import app
    print("Starting Telegram Bot from bot.py...")
    await app.start()
    
    # Keep the event loop running
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
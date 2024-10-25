from concurrent.futures import ThreadPoolExecutor
import asyncio

from api_service.automate_process import ContentAutomation

executor = ThreadPoolExecutor(max_workers=2)

async def run_content_automation_task():
    """ Runs the automation process as a background task using ThreadPoolExecutor. """
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(executor, run_automation)

def run_automation():
    """Synchronous wrapper for running the content automation."""
    automation = ContentAutomation()
    asyncio.run(automation.run())  # Ensuring asyncio loop for background task

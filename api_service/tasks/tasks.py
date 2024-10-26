from concurrent.futures import ThreadPoolExecutor
import asyncio

from api_service.automate_process import ContentAutomation

executor = ThreadPoolExecutor(max_workers=2)

async def run_content_automation_task():
    """ Runs the automation process as a background task using ThreadPoolExecutor. """
    content_automation = await ContentAutomation.create()
    await content_automation.run()

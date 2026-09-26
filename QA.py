"""https://global.baidu.com/s?wd=%E8%A7%A3%E7%AD%94%E4%BB%A5%E4%B8%8B%E9%97%AE%E9%A2%98%EF%BC%8C%E7%AD%94%E6%A1%88%E4%BB%A5%E9%80%89%E9%A1%B9%E6%A0%BC%E5%BC%8F%E7%BB%99%E6%88%91%3A%20%E5%AE%9E%E7%89%A9%E8%B5%84%E6%96%99%E5%8C%85%E6%8B%AC%E9%81%97%E8%BF%B9%E5%92%8C%E9%81%97%E7%89%A9%2C%E5%8F%88%E7%BB%9F%E7%A7%B0%E4%B8%BA%E9%81%97%E5%AD%98%20A%E6%98%AF%20B%E5%90%A6"""

from playwright.async_api import async_playwright
import asyncio
from playwright_stealth import Stealth
import random
import requests


class Question_answer:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.console = None
        self.page = None
        self.lock = asyncio.Lock()

    async def open(self):
        self.playwright = await async_playwright().start()

        launch_config = {
            'headless': False,
            'args': [
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-web-security',
                '--disable-dev-shm-usage',
                '--autoplay-policy=no-user-gesture-required',
                '--allow-autoplay',
                '--disable-audio-output-restrictions',
                '--enable-features=OverlayScrollbar',
                '--disable-features=PreloadMediaEngagementData,MediaEngagementBypassAutoplayPolicies',
                '--disable-ipc-flooding-protection',
                '--disable-background-timer-throttling',
                '--disable-extensions',
                '--disable-infobars',
                '--start-maximized',
                '--disable-media-autoplay-restrictions',
                '--mute-audio'  # 开启禁音
            ],
            'ignore_default_args': [
                '--enable-automation'
            ]
        }

        proxys = [
            {'server': 'http://122.9.131.161:1080'},
            {'server': 'http://39.104.57.170:3000'},
            {'server': 'http://120.232.115.57:17981'},
            {'server': 'http://39.104.57.170:9002'},
            {'server': 'http://223.113.241.216:59999'},
        ]

        config = {
            'viewport': {'width': 1400, 'height': 850},
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
            'permissions': ["notifications"],
            'locale': "zh-CN",
            'timezone_id': "Asia/Shanghai",
            # 'proxy': random.choice(proxys)
        }

        self.browser = await self.playwright.chromium.launch(**launch_config)
        self.context = await self.browser.new_context(**config)

        await Stealth().apply_stealth_async(self.context)

        self.page = await self.context.new_page()
        await self.page.goto("https://global.baidu.com/")

    async def baidu_url(self, question):
        question_prompt = f"解答以下问题,答案以选项格式给我：{question}"

        async with self.lock:
            textarea = self.page.locator("textarea#chat-textarea")
            await textarea.fill("")
            await textarea.press_sequentially(question_prompt, delay=100)    # 改为逐字输入

            await self.simulate_human_click(self.page.locator("button#chat-submit-button"), self.page)
            # await asyncio.sleep(2)
            # await self.simulate_human_click(self.page.locator("button#chat-submit-button"), self.page)

            await asyncio.sleep(5)
            try:
                answer = await self.page.locator("mark.flexible-marker.flexible-marker-default").locator("strong").inner_text(timeout=3000)
            except:
                answer = await self.page.locator("p.marklang-paragraph").first.inner_text()
            print(answer)

        return answer

    async def simulate_human_click(self, button_locator, page=None):
        """模拟人类鼠标点击（移动-按下-松开）"""
        if page is None:
            page = self.page

        # 等待按钮可点击
        await button_locator.wait_for(state="visible", timeout=5000)
        box = await button_locator.bounding_box()

        if not box:
            print("坐标未加载")
            return False

        # 随机偏移
        click_x = box["x"] + box["width"] / 2 + random.randint(-3, 3)
        click_y = box["y"] + box["height"] / 2 + random.randint(-3, 3)

        # 模拟人类操作节奏
        await page.mouse.move(click_x, click_y)
        await asyncio.sleep(random.uniform(0.1, 0.3))
        await page.mouse.down()
        await asyncio.sleep(random.uniform(0.05, 0.2))
        await page.mouse.up()
        await asyncio.sleep(random.uniform(0.2, 0.5))
        await page.mouse.move(random.randint(0, 900), random.randint(0, 500))

    async def close(self):
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()




async def main():
    question_app = Question_answer()
    await question_app.open()
    question = "实物资料包括遗迹和遗物，又统称为遗存。A、对B、错"
    answer = await question_app.baidu_url(question)
    await question_app.close()


if __name__ == "__main__":
    asyncio.run(main())
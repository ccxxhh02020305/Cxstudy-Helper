import asyncio
from playwright.async_api import async_playwright
import keyboard
import os
import random
import threading
import time



def enable_console_log(filename="控制台日志.txt"):
    import atexit
    import sys
    from pathlib import Path
    from threading import Lock

    class Tee:
        def __init__(self, console, log_file):
            self.console = console
            self.log_file = log_file
            self.lock = Lock()

        def write(self, text):
            with self.lock:
                self.console.write(text)
                self.log_file.write(text)
                self.log_file.flush()
            return len(text)

        def flush(self):
            self.console.flush()
            self.log_file.flush()

        def __getattr__(self, name):
            return getattr(self.console, name)

    log_path = Path(__file__).resolve().with_name(filename)
    log_file = log_path.open("a", encoding="utf-8", buffering=1)

    old_stdout = sys.stdout
    old_stderr = sys.stderr

    sys.stdout = Tee(old_stdout, log_file)
    sys.stderr = Tee(old_stderr, log_file)

    def close_log():
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        log_file.close()

    atexit.register(close_log)







class BrowserManager:
    def __init__(self, url=None):
        self.loop = None
        self.stop_event = None
        self.closed = False
        self.url = url
        self.playwright = None
        self.context = None
        self.page = None
        self.video_status = False
        self.start_time = None
        self.counter_task = None
        self.is_running = True
        self.is_checking = False
        self.user_data_dir = "C:\\Temp\\PlaywrightUserDir"
        os.makedirs(self.user_data_dir, exist_ok=True)

    async def open_chromium(self, url=None):
        self.loop = asyncio.get_running_loop()
        self.stop_event = asyncio.Event()

        # ESC键监听
        def listen_esc():
            while self.is_running:
                if keyboard.is_pressed('esc'):
                    print("\n检测到ESC键，正在关闭浏览器...")
                    self.loop.call_soon_threadsafe(self.stop_event.set)
                    return

            time.sleep(0.05)
        threading.Thread(target=listen_esc, daemon=True).start()



        target_url = url
        self.playwright = await async_playwright().start()

        # 启动参数
        launch_config = {
            'user_data_dir': self.user_data_dir,
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
                '--disable-media-autoplay-restrictions'
            ],
            'ignore_default_args': [                      # 默认禁音
                '--enable-automation'
            ],
            'viewport': {'width': 1920, 'height': 768 },
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
            'permissions': ["notifications"],
            'locale': "zh-CN",
            'timezone_id': "Asia/Shanghai"
        }


        # 启动持久化上下文
        self.context = await self.playwright.chromium.launch_persistent_context( **launch_config)
        # 监听新标签页的创建（课程详情）
        self.context.on("page", lambda new_page: asyncio.create_task(self.setup_new_page(new_page)))

        # 创建页面
        self.page = await self.context.new_page()

        # 环境伪装
        await self.page.add_init_script("""
                    delete window.navigator.webdriver;
                    Object.defineProperty(window.navigator, 'language', {value: 'zh-CN'});
                    Object.defineProperty(window.navigator, 'languages', {value: ['zh-CN', 'zh']});
                    Object.defineProperty(window.screen, 'width', {value: 1920});
                    Object.defineProperty(window.screen, 'height', {value: 1080});
                """)

        # # 事件监听：每次主框架导航完成后自动检测
        # self.page.on("framenavigated", self.on_frame_navigated)
        # 访问超星课程页面
        await self.page.goto(target_url, timeout=60000, wait_until="networkidle")

        # 模拟点击播放
        try:
            await asyncio.sleep(10)
            await self.task_list()
        except Exception as e:
            print(f"执行任务列表出错：{e}")



    async def scan_page(self, page=None):
        """确定未完成任务数量"""
        if page is None:
            page = self.page

        # 确保当前页面是学习页面，如果不是则等待
        try:
            await page.wait_for_url("**/mycourse/studentstudy**", timeout=15000)
        except Exception:
            print("当前页面不是学习页面，跳过任务检测")
            return None, None

        # 等待iframe出现
        try:
            main_iframe = page.frame_locator("iframe#iframe")  # 最外层套了一个<iframe> id="iframe"
            div_locator = main_iframe.locator("div[aria-label='任务点未完成']")
            div_count = await div_locator.count()
            print(f"本页检测到{div_count}个任务")
            span_locator = page.locator("span.orangeNew")

            # div_locator = page.locator("div.ans-cc#pageDiv")   # <div> class="ans-cc" id="pageDiv"
            return div_locator, div_count

        except Exception as e:
            print(f"定位主iframe失败：{e}")
            await page.reload(timeout=15000)
            return None, None

    async def video_task(self, i, page, div_locator):
        """滑动并点击播放视频"""
        parent_locator = div_locator.nth(i).locator("xpath=..")  # 返回父级，包含未完成标记和视频iframe
        try:
            await parent_locator.scroll_into_view_if_needed(timeout=5000)
            await page.wait_for_timeout(1000)
            video_iframe = parent_locator.frame_locator("iframe")
            video_button = video_iframe.locator("button.vjs-big-play-button")  # 定位器
            await video_button.wait_for(state="attached", timeout=5000)
            await video_button.scroll_into_view_if_needed(timeout=5000)        # 滚动直至可视
            await self.simulate_human_click(video_button, page)
            self.video_status = await self.change_video_status(page, video_iframe)        # 改变视频状态
            return self.video_status, video_iframe

        except Exception as e:
            print(f"滑动寻找按钮失败：{e}")
            # await page.reload(timeout=15000)
            return None, None


    async def task_list(self, page=None):
        """主任务列表"""
        if page is None:
            page = self.page
        div_locator, div_count = await self.scan_page(page)


        if (div_locator, div_count) == (None, None):
            return

        if self.counter_task == None:
            self.counter_task = asyncio.create_task(self.min_counter(page))

        for i in range(div_count):
            try:
                self.video_status, video_iframe = await self.video_task(0, page, div_locator)  # 为防止动态的div_locator索引越界，硬编码 i 为 0
                while(self.video_status):
                    await asyncio.sleep(10)
                    self.video_status = await self.change_video_status(page, video_iframe)
            except Exception as e:
                print(f"第{i+1}个视频播放失败，{e}")
                continue

        await self.change_video_page(page)

    async def F5(self, page):
        now = time.monotonic()

        if self.video_status:         # 视频正在播放，清除未播放计时
            self.start_time = None
            return
        if self.start_time is None:   # 第一次检测到视频停止
            self.start_time = now
            print("检测到视频停止，开始计时")
            return
        if now - self.start_time >= 300:
            print("视频已连续5分钟未播放，刷新页面")

            try:
                await page.reload(timeout=15000, wait_until="domcontentloaded")
            except Exception as e:
                print(f"刷新页面失败：{e}")
            finally:
                self.start_time = None

    async def min_counter(self, page):
        while self.is_running:
            await self.F5(page)
            await asyncio.sleep(10)

    async def change_video_status(self, page, iframe):     # <div> class="vjs-control-bar"里有个<span> class="vjs-control-text"，若内容为暂停，则正在播放，实时变化
        """视频状态变化"""
        div_locator = iframe.locator("button.vjs-play-control")
        video_status_locator = div_locator.locator("span.vjs-control-text")
        video_status = await video_status_locator.text_content()
        if video_status == "暂停":
            video_status = True
        else:
            video_status = False

        return video_status

    async def change_video_page(self, page):        # <span> class="orangeNew"内数量不为 0 即有任务
        """"该页视频播放完后换页"""
        # span_locator_count = await span_locator.count()          # <div> class="posCatalog_select posCatalog_active" 即正在此页播放课程
        now_div_locator = page.locator("div.posCatalog_select.posCatalog_active")          # 现在所在的节
        now_second_li_locator = now_div_locator.locator("xpath=..")                        # 该节的li
        next_Li = now_second_li_locator.locator("xpath=following-sibling::li[.//span[contains(@class, 'orangeNew')]][1]")
        em_locator = next_Li.locator("em.posCatalog_sbar")               # 存在第三级的可能性

        if await next_Li.count() > 0:                                    # 该章内，本li后还有下一个li；或有第三级目录
            unfinished_span = next_Li.locator("span.orangeNew").first
            task_li = unfinished_span.locator("xpath=ancestor::li[1]")
            target_em = task_li.locator(":scope > div em.posCatalog_sbar").first
            await target_em.scroll_into_view_if_needed(timeout=5000)     # 滚动直至可视
            await self.simulate_human_click(target_em, page)

        else:                                                            # 需要换到下一章
            chapter_li_locator = now_second_li_locator.locator("xpath=../../..")  # 整个课程的li列表，每一个li都是一章
            next_chapter_locator = chapter_li_locator.locator("xpath=following-sibling::li[1]")
            next_chapter_first_span = next_chapter_locator.locator("span.orangeNew").first
            while await next_chapter_first_span.count() == 0:            # 防止下一章没有未完成任务点，一直向下找
                next_2_chapter_locator = next_chapter_locator.locator("xpath=following-sibling::li[1]")
                next_chapter_first_span = next_2_chapter_locator.locator("span.orangeNew").first
                next_chapter_locator = next_2_chapter_locator
                if await next_chapter_locator.count() == 0:
                    print("没有下一章了")
                    return
            next_chapter_first_div = next_chapter_first_span.locator("xpath=../..")
            next_em_locator = next_chapter_first_div.locator("em.posCatalog_sbar")
            await next_em_locator.scroll_into_view_if_needed(timeout=5000)         # 滚动直至可视
            await self.simulate_human_click(next_em_locator, page)


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




    async def setup_new_page(self, new_page):
        """为每个新打开的标签页配置自动检测"""
        print(f"检测到新标签页打开：{new_page.url}")

        # 注入反检测脚本（与主页面相同）
        await new_page.add_init_script("""
            delete window.navigator.webdriver;
            Object.defineProperty(window.navigator, 'language', {value: 'zh-CN'});
            Object.defineProperty(window.navigator, 'languages', {value: ['zh-CN', 'zh']});
            Object.defineProperty(window.screen, 'width', {value: 1920});
            Object.defineProperty(window.screen, 'height', {value: 1080});
        """)

        # 等待页面加载完毕
        try:
            await new_page.wait_for_load_state("networkidle", timeout=30000)
        except Exception as e:
            # await new_page.reload(timeout=15000)
            print(f"新页面加载超时：{e}")

        # 为新页面添加导航监听（支持后续跳转）
        new_page.on("framenavigated", lambda frame: asyncio.create_task(self.on_frame_navigated(frame, page=new_page)))

        # 执行首次任务检测
        await asyncio.sleep(1)  # 等待动态内容渲染
        await self.auto_check_tasks(page=new_page)  # 需要对原有方法支持指定 page

    async def on_frame_navigated(self, frame, page=None):
        if page is None:
            page = self.page
        if frame != page.main_frame:
            return
        print(f"检测到页面跳转至：{frame.url}")
        await asyncio.sleep(2)
        asyncio.create_task(self.auto_check_tasks(page=page))

    async def auto_check_tasks(self, page=None):
        if page is None:
            page = self.page
        if self.is_checking:
            return
        self.is_checking = True
        try:
            await self.task_list(page=page)
        except Exception as e:
            print(f"自动检测任务出错：{e}")
        finally:
            self.is_checking = False



    async def close_chromium(self):
        """安全关闭所有资源"""
        self.is_running = False
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.playwright:
                await self.playwright.stop()
            print("浏览器已完全关闭")
        except Exception as e:
            print(f"关闭资源出错：{e}")

    async def wait_for_close(self):
        """等待键盘线程发送关闭信号"""
        await self.stop_event.wait()


async def main():
    course_url = "https://v8.chaoxing.com/"  # 超星课程具体URL

    try:
        print("正在启动浏览器，适配超星学习通...")
        browser = BrowserManager(url=course_url)
        await browser.open_chromium(course_url)
        print("\n浏览器已打开！")
        print("按ESC键关闭浏览器")
        await browser.wait_for_close()
    except Exception as e:
        print(f"\n程序运行出错：{e}")
        import traceback
        traceback.print_exc()
    finally:
        await browser.close_chromium()


if __name__ == "__main__":
    enable_console_log()
    asyncio.run(main())
import sys
import asyncio

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QLabel,
)
from qasync import QEventLoop, asyncSlot
from 学习不通 import BrowserManager


class UiOutput(QObject):
    text_received = Signal(str)

    def write(self, text):
        if text:
            self.text_received.emit(text)

    def flush(self):
        pass


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.browser_manager = None          # 当前BrowserManager实例
        self.browser_task = None             # 正在运行的异步浏览器任务

        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr

        self.setWindowTitle("学习不通控制台")
        self.setGeometry(980, 50, 420, 850)

        self.status_label = QLabel("当前状态：未启动")

        self.start_button = QPushButton("启动浏览器")
        self.stop_button = QPushButton("停止")
        self.stop_button.setEnabled(False)

        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumBlockCount(3000)     # 最多保留3000个文本块

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.status_label)
        layout.addLayout(button_layout)
        layout.addWidget(self.console)

        # 只接管 stdout
        self.ui_output = UiOutput()
        self.ui_output.text_received.connect(self.console.insertPlainText)
        sys.stdout = self.ui_output

        # stderr 保持原样，不进入文本框
        sys.stderr = self.original_stderr

        self.start_button.clicked.connect(self.start_browser)
        self.stop_button.clicked.connect(self.stop_browser)

    @asyncSlot()
    async def start_browser(self):
        if self.browser_task and not self.browser_task.done():
            return

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setText("当前状态：正在启动")

        # BrowserManager 使用原来的类
        self.browser_manager = BrowserManager(url="https://v8.chaoxing.com/")
        self.browser_task = asyncio.create_task(self.run_browser())

    async def run_browser(self):
        try:
            await self.browser_manager.open_chromium(self.browser_manager.url)

            self.status_label.setText("当前状态：浏览器运行中")
            print("浏览器启动完成\n")

            await self.browser_manager.wait_for_close()    # 等待停止

        except asyncio.CancelledError:
            print("浏览器任务已取消\n")
            raise

        except Exception as e:
            # 错误进入系统控制台，不进入下侧文本框
            print(
                f"浏览器运行错误：{e}",
                file=sys.stderr
            )

        finally:
            if self.browser_manager:
                await self.browser_manager.close_chromium()

            self.status_label.setText("当前状态：已停止")
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)

    @asyncSlot()
    async def stop_browser(self):
        self.stop_button.setEnabled(False)

        if self.browser_manager:
            self.browser_manager.is_running = False

            if self.browser_manager.stop_event:
                self.browser_manager.stop_event.set()

            await self.browser_manager.close_chromium()

        if self.browser_task and not self.browser_task.done():
            self.browser_task.cancel()

            try:
                await self.browser_task
            except asyncio.CancelledError:
                pass

        self.browser_manager = None
        self.browser_task = None

    def closeEvent(self, event):
        # closeEvent 本身不能 await，安排异步关闭
        if self.browser_manager:
            asyncio.create_task(self.browser_manager.close_chromium())

        if self.browser_task and not self.browser_task.done():
            self.browser_task.cancel()

        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr

        event.accept()

def main():
    app = QApplication(sys.argv)

    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = MainWindow()
    window.show()

    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()
from src.tasks.BaseEfTask import BaseEfTask
from src.data.FeatureList import FeatureList as fL
import re

class Test(BaseEfTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "测试"

    def test_ocr(self):
        box1 = self.box_of_screen(1749 / 1920, 107 / 1080, 1789 / 1920, 134 / 1080)
        box2 = self.box_of_screen(
            (1749 + (1832 - 1750)) / 1920,
            107 / 1080,
            (1789 + (1832 - 1750)) / 1920,
            134 / 1080,
        )
        self.wait_click_ocr(
            match=re.compile(r"^\d+/5$"),
            after_sleep=2,
            time_out=2,
            box=box1,
            log=True,
        )
        self.wait_click_ocr(
            match=re.compile(r"^\d+/5$"),
            after_sleep=2,
            time_out=2,
            box=box2,
            log=True,
        )

    def run(self):
        self.ensure_main()
        self.send_key("i",after_sleep=2)
        exchange_help_box = self.box_of_screen(0.1, 561 / 861, 0.9, 0.9)
        if self.wait_click_ocr(match=re.compile("会客室"), time_out=4, box=exchange_help_box,after_sleep=2):
            self.logger.info("进入会客室,准备处理收集线索")
            self.wait_click_ocr(match=re.compile("确认"), time_out=4, box=self.box.bottom,after_sleep=2)
            if self.wait_click_ocr(match=re.compile("收集"), time_out=4, box=self.box.right,after_sleep=2):
                self.logger.info("点击收集线索")
                self.wait_click_ocr(match=re.compile("领取"), time_out=4, box=self.box.right,after_sleep=2)
                self.back(after_sleep=1)

            if self.wait_click_ocr(match=re.compile("接收"), time_out=4, box=self.box.right,after_sleep=2):
                self.wait_click_ocr(match=re.compile("全部接收"), time_out=4, box=self.box.right,after_sleep=2)
                self.back(after_sleep=2)
            results = []

            search_box = self.box_of_screen(
                x=1390 / 3840, y=450 / 2160, to_x=3360 / 3840, to_y=1330 / 2160
            )

            for i in range(1, 8):
                self.next_frame()
                result = self.find_one(
                    feature_name=f"clue_{i}_icon",
                    box=search_box,
                )
                if result:
                    results.append(result)
                    self.sleep(0.5)

            for result in results:
                self.logger.info("点击线索框")
                self.click(result)
                self.wait_click_ocr(match=re.compile("的线索"),time_out=4, box=self.box.top_right,after_sleep=1)
                if not self.wait_ocr(match=[re.compile(i) for i in ["设施","等级"]],box=self.box.left, time_out=1):
                    self.back(after_sleep=2)
            results=self.wait_click_ocr(match=re.compile("开展交流"), time_out=4, box=self.box.bottom,after_sleep=1)
            self.wait_pop_up()

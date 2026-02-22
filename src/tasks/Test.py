import time
from src.interaction.ScreenPosition import ScreenPosition as sP
from src.tasks.BaseEfTask import BaseEfTask
from src.interaction.Mouse import active_and_send_mouse_delta,run_at_window_pos
from src.data.features import FeatureList
import pyautogui
import re
from src.image.hsv_config import HSVRange as hR
from src.data.world_map import exchange_goods_dict
on_zip_line_tip = ["移动鼠标", "选择前进目标", "向目标移动", "离开滑索架"]
on_zip_line_stop = [re.compile(i) for i in on_zip_line_tip]
class Test(BaseEfTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.name = "测试"
    def get_goods_piece(self):
        test_goods=exchange_goods_dict["四号谷地"]
        test_goods_re=[re.compile(i[0:3]) for i in test_goods]
        self.next_frame()
        results=self.ocr(match=test_goods_re,log=True)
        for result in results:
            self.click(result,after_sleep=1)
            self.next_frame()
            result1=self.ocr(match=re.compile(r"^\d+$"),box=self.box_of_screen(1527/1920,367/1080,1600/1920,400/1080),log=True)
            self.wait_click_ocr(match=re.compile("查看好友价格"),box=sP.bottom_right,after_sleep=2)
            self.next_frame()
            result2=self.ocr(match=re.compile(r"\d+$"),box=self.box_of_screen(800/1920,430/1080,1270/1920,490/1080),frame_processor=self.make_hsv_isolator(hR.DARK_GRAY_TEXT),log=True)
            if not result:
                result=[]
            if not result2:
                result2=[]
            self.log_info(
                f"货物名称: {result.name}, "
                f"价格: {[i.name for i in result1]}, "
                f"价格来源人和价格: {[i.name for i in result2]}"
            )
            self.back(after_sleep=0.5)
            self.back(after_sleep=0.5)
    def to_friend_exchange(self):
        start_time = time.time()
        while not self.wait_ocr(match=re.compile("物资调度终端"), box=sP.BOTTOM_RIGHT.value, time_out=1):
            if time.time() - start_time > 200:
                self.log_info("前往干员联络站超时")
                return
            if not short_distance_flag:
                nav = self.find_feature(
                    "market_dispatch_terminal_out",
                    box=self.box_of_screen(
                        (1920 - 1550) / 1920,
                        150 / 1080,
                        1550 / 1920,
                        (1080 - 150) / 1080,
                    ),
                    threshold=0.7,
                )
                if nav:
                    fail_count = 0
                    self.log_info("找到导航路径，继续对齐并前进")
                    self.align_ocr_or_find_target_to_center(
                        ocr_match_or_feature_name_list="market_dispatch_terminal_out",
                        only_x=True,
                        threshold=0.7,
                        ocr=False,
                    )
                    self.move_keys("w", duration=1)
                else:
                    fail_count += 1
                    self.log_info(f"未找到导航路径，连续失败次数: {fail_count}")
                    if fail_count >= 3:
                        self.log_info("长时间未找到导航，切换短距离移动")
                        short_distance_flag = True
                    self.move_keys("w", duration=0.5)
            else:
                self.move_keys("w", duration=0.5)
        self.send_key("f", after_sleep=2)
    def run(self):
        pass
        

        # 搜索特定好友逻辑
        # self.wait_click_ocr(match=re.compile('输入名称'), settle_time=0.5)
        # self.input_text('test')


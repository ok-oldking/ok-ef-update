import re
import time
import pyautogui
from src.tasks.BaseEfTask import BaseEfTask
from src.data.FeatureList import FeatureList as fL
from src.interaction.Mouse import run_at_window_pos
from ok import Box

class LoginMixin(BaseEfTask):

    def login_flow(self, username: str, password: str | None = None):
        """
        执行登录流程：登出当前账号并尝试用指定账号登录。

        该方法会：
        - 检查是否已登录并返回主界面；
        - 点击“最近”列表并尝试选择指定账号后登录；
        - 等待登录成功或超时并返回结果/抛出异常。

        Args:
            username (str): 要登录的账号标识（一般为手机号）。可传完整手机号或仅后四位。
            password (str | None): 兼容旧接口的参数，可传入但不会被存储或用于身份判定（保留以便向后兼容）。

        Returns:
            None

        Raises:
            RuntimeError: 在未找到登出按钮或登录确认失败时抛出异常。

        Notes:
            - 选择账号时先尝试使用完整 `username` 匹配；若 UI 中仅能识别后四位且后四位在列表中唯一，则使用后四位进行点击匹配。
            - 由于 OCR/界面识别的不确定性，使用后四位匹配存在点击到错误账号的风险；建议确保最近账号列表中后四位唯一。
        """
        self._logged_in = False
        start_time = time.time()
        while time.time() - start_time < 3:
            result = self.wait_ocr(match=re.compile("ms"), time_out=1, box=self.box.bottom_left)
            if result:
                self._logged_in = True
                break
            self.sleep(1)
        if self._logged_in:
            self.ensure_main()
            self.back(after_sleep=2)
            for _ in range(5):
                result = self.find_one(fL.main_out, vertical_variance=0.05, horizontal_variance=0.1, threshold=0.6)
                if result:
                    break
                self.sleep(1)
            if result:
                self.click(result, after_sleep=1)
                self.click_confirm()
            else:
                self.log_error("未找到主界面退出按钮，可能未成功返回登录界面")
        start_time = time.time()
        while time.time() - start_time < 120:
            result = self.find_feature(feature_name=fL.logout)
            self.sleep(1)
            if result:
                break
        if not result:
            raise RuntimeError("未找到登出按钮，可能没有先登录，请先登录任意账号")
        self.click(result[0], after_sleep=1)
        self.active_and_send_mouse_delta(0, 0, activate=True, only_activate=True)
        self.wait_click_ocr(match=re.compile("确认"), time_out=10, box=self.box.bottom_right, after_sleep=2)
        self._logged_in = False
        result=self.click_text(re.compile("最近"), box=self.box.center, need_wait_disappear=False)  # 点击当前账号（假设是唯一的）"最近", box=self.box.center, need_wait_disappear=False)  # 点击当前账号（假设是唯一的）
        if not result:
            self.log_error("未找到‘最近’按钮，可能未成功返回登录界面")
            raise RuntimeError("未找到‘最近’按钮，可能未成功返回登录界面")
        self.click_text(re.compile(username[-4:]), box=self.box_of_screen(0, (result[0].y+result[0].height)/self.height, 1, 1))  # 点击最近登录的账号（假设是唯一的）
        self.click_text("登录")
        if not self._confirm_logged_in():
            raise RuntimeError("登录失败")
    def _confirm_logged_in(self, time_out: int = 120) -> bool:
        """
        等待并确认当前是否已登录（通过查找登出按钮判断）。

        Args:
            time_out (int): 最长等待秒数，超过则返回 False。

        Returns:
            bool: 如果在超时时间内检测到登出按钮返回 True，否则返回 False。

        Notes:
            - 该方法会在检测到登出按钮后立即返回 True；未检测到则记录错误日志并返回 False。
        """
        start_time = time.time()
        while time.time() - start_time < time_out:
            result = self.find_feature(feature_name=fL.logout)
            if result:
                self.log_info("登录成功")
                return True
            self.sleep(1)
        self.log_error("登录确认超时，疑似登录失败")
        return False

    def _type_text(self, text: str) -> None:
        """
        将给定文本粘贴到当前焦点控件以实现可靠输入（支持中文）。

        说明：使用剪贴板+粘贴的方式比逐字符模拟输入更可靠，尤其在输入中文或特殊字符时。

        Args:
            text (str): 要输入的文本。

        Returns:
            None
        """
        import pyperclip

        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
    def click_text(self, match: str, box=None, need_wait_disappear: bool = True) -> Box|None:
        """
        在指定区域使用 OCR 查找并点击包含指定文本的 UI 元素，支持重试与确认消失逻辑。

        Args:
            text (str): 要点击的文本（支持正则匹配传入字符串会被编译为正则）。
            box (Optional[BoxLike]): 搜索的区域，默认为 `self.box.bottom`。
            need_wait_disappear (bool): 如果为 True，则点击后会等待该文本从界面上消失以确认点击生效；为 False 时立即返回。

        Returns:
            Box|None: 如果成功点击则返回点击的结果box；如果 `need_wait_disappear` 为 True，则在目标消失后返回点击的结果box。超时或未点击返回 None。

        Notes:
            - 方法内部会进行最多 60 秒的重试；成功条件为至少点击过一次（或在未找到时认为未点击）。
            - 当 `need_wait_disappear` 为 True 时，方法会在点击后等待目标从界面上消失以确认生效。
        """
        if box is None:
            box = self.box.bottom
        start_time = time.time()
        clicked = False
        while time.time() - start_time < 60:
            ocr_result = self.login_ocr(match=match, box=box, need_active=False)   

            if not ocr_result:
                # 未找到目标
                if clicked:
                    # 已经点击过
                    if need_wait_disappear:
                        # 需要确认消失：目标已不在界面，视为成功
                        self.log_info(f"点击并确认目标已消失: {match}")
                        return ocr_result
                    else:
                        # 无需等待消失，已点击即为成功
                        return ocr_result
                # 未点击过，继续等待
                self.sleep(1)
                continue

            # 找到目标，执行点击
            if ocr_result:
                run_at_window_pos(
                    self.hwnd.hwnd,
                    pyautogui.click,
                    ocr_result[0].x + ocr_result[0].width // 2,
                    ocr_result[0].y + ocr_result[0].height // 2,
                )
            clicked = True

            self.sleep(1)  # 给UI反应时间

            if not need_wait_disappear:
                return ocr_result

            # 需要等待消失，继续循环检查是否消失
            check = self.login_ocr(match=match, box=box, need_active=False)
            if not check:
                self.log_info(f"点击后目标已消失: {match}")
                return ocr_result

            # 还在 → 说明没点到 / 没反应，记录并重试
            self.log_debug("点击后仍检测到‘" + match + "’，准备重试")
            self.sleep(1)

        # 超时结束：如果曾经点击过且不要求消失，则也返回 True（上方已处理），否则返回 False
        if clicked and not need_wait_disappear:
            return ocr_result
        self.log_error("点击" + match + "超时或未成功")
        return None

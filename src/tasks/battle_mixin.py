import time
import re
import cv2
import numpy as np
import threading

from src.tasks.AutoCombatLogic import AutoCombatLogic
from src.tasks.BaseEfTask import BaseEfTask

yellow_skill_color = {"r": (230, 255), "g": (180, 255), "b": (0, 85)}

white_skill_color = {"r": (190, 255), "g": (190, 255), "b": (190, 255)}

lower_white_none_inclusive = np.array([222, 222, 222], dtype=np.uint8)
black = np.array([0, 0, 0], dtype=np.uint8)


def isolate_white_text_to_black(cv_image):
    match_mask = cv2.inRange(cv_image, black, lower_white_none_inclusive)
    output_image = cv2.cvtColor(match_mask, cv2.COLOR_GRAY2BGR)
    return output_image


def has_rectangles(frame):
    if frame is None:
        return False
    original_h, original_w = frame.shape[:2]
    scale_factor = 4
    resized = cv2.resize(frame, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 100)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    closed_edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(closed_edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_width = (original_w * scale_factor) * 0.25
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        if w > min_width and w > h and h > 10:
            return True
    return False


class BattleMixin(BaseEfTask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ocr_lock = threading.Lock()  # OCR 锁
        self.exit_check_count = 0
        self.last_op_time = 0
        self.last_no_number_action_time = 0
        self.last_skill_time = 0

    # ---------------- 技能序列 ----------------
    def _parse_skill_sequence(self, raw_config: str) -> list[str]:
        if not raw_config:
            return []
        trimmed_config = raw_config.strip()
        sequence = [c for c in trimmed_config if c in {"1", "2", "3", "4"}]
        return sequence if sequence else ["1", "2", "3"]

    def wait_in_combat(self, time_out=3, click=False, frame_copy=None):
        start = time.time()
        while time.time() - start < time_out:
            if self.in_combat(frame_copy=frame_copy):
                return True
            else:
                self.sleep(0.003)
        return False

    def use_ult(self, frame_copy=None):
        ults = ["1", "2", "3", "4"]
        for ult in ults:
            if self.find_one("ult_" + ult, frame=frame_copy):
                self.send_key_down(ult)
                self.wait_until(lambda: not self.in_combat(frame_copy=frame_copy))
                self.send_key_up(ult)
                self.wait_in_combat(time_out=8, frame_copy=frame_copy)
                self.last_op_time = time.time()
                return True
        return False

    def use_link_skill(self, frame_copy=None):
        if self.find_one("default_link_skill", threshold=0.7, frame=frame_copy):
            self.send_key("e")
            self.last_op_time = time.time()
            return True
        return False

    # ---------------- 战斗状态 ----------------
    def in_combat(self, required_yellow=0, frame_copy=None):
        return (
            self.get_skill_bar_count(frame_copy=frame_copy) >= required_yellow
            and self.in_team(frame_copy=frame_copy)
            and not self.ocr_lv(frame_copy=frame_copy)
        )

    def in_team(self, frame_copy=None):
        return all([self.find_one(f"skill_{i}", frame=frame_copy) is not None for i in range(1, 5)])

    def is_combat_ended(self, frame_copy=None):
        if self._check_single_exit_condition(frame_copy):
            self.exit_check_count += 1
            if self.exit_check_count >= 2:
                self.exit_check_count = 0
                return True
        else:
            self.exit_check_count = 0
        return False

    def _check_single_exit_condition(self, frame_copy=None):
        skill_count = self.get_skill_bar_count(frame_copy=frame_copy)
        if skill_count >= 0:
            if getattr(self, "_last_exit_fail_skill_count", None) != skill_count:
                self.log_info(f"退出检查失败: 技能条仍有效 (count={skill_count})")
                self._last_exit_fail_skill_count = skill_count
            return False
        self._last_exit_fail_skill_count = None

        has_lv = self.ocr_lv(frame_copy=frame_copy)
        in_team = self.in_team(frame_copy=frame_copy)
        if not (has_lv or not in_team):
            self.log_info(f"退出检查失败: UI状态不符 (has_lv={has_lv}, in_team={in_team})")
            return False

        has_center_number = self._check_center_area_has_number(frame_copy=frame_copy)
        if has_center_number:
            self.log_info("退出检查失败: 中间区域仍有伤害数字")
            return False

        self.log_info(
            f"退出检查通过: skill_count={skill_count}, has_lv={has_lv}, in_team={in_team}, center_number={has_center_number}"
        )
        return True

    # ---------------- OCR ----------------
    def ocr_lv(self, frame_copy=None):
        with self.ocr_lock:
            lv = self.ocr(0.02, 0.89, 0.23, 0.93, match=self.lv_regex, name="lv_text", frame=frame_copy)
            if lv:
                return True
            lv = self.ocr(
                0.02,
                0.89,
                0.23,
                0.93,
                frame_processor=isolate_white_text_to_black,
                match=self.lv_regex,
                name="lv_text",
                frame=frame_copy,
            )
            return bool(lv)

    def _check_center_area_has_number(self, frame_copy=None):
        try:
            with self.ocr_lock:
                box = self.box_of_screen(0.20, 0.0, 0.80, 0.65)
                self.next_frame()
                center_area = self.ocr(match=r"^\d+$", box=box, name="center_number", frame=frame_copy)
                if center_area:
                    self.log_info(f"中间区域识别到数字: {[r.name for r in center_area]}")
                return bool(center_area)
        except Exception:
            return False

    # ---------------- 普攻/闪避 ----------------
    def perform_attack_weave(self):
        """执行普通攻击，如果操作间隔允许"""
        self.click(move=False, key='left',after_sleep=0.005)


    def handle_no_damage_number_actions(self):
        """周期触发向前闪避"""
        self.log_info("执行索敌+向前闪避")
        self.click(key="middle", down_time=0.002)
        self.dodge_forward(pre_hold=0.05, dodge_down_time=0.03, after_sleep=0.02)
        

    # ---------------- 技能条 ----------------
    def get_skill_bar_count(self, frame_copy=None):
        skill_area_box = self.box_of_screen_scaled(3840, 2160, 1586, 1940, 2266, 1983)
        skill_area = skill_area_box.crop_frame(frame_copy if frame_copy is not None else self.frame)
        if not has_rectangles(skill_area):
            return -1
        count = 0
        y_start, y_end = 1958, 1970
        bars = [(1604, 1796), (1824, 2013), (2043, 2231)]
        for x1, x2 in bars:
            if self.check_is_pure_color_in_4k(x1, y_start, x2, y_end, yellow_skill_color):
                count += 1
            else:
                break
        if count == 0:
            has_white_left = self.check_is_pure_color_in_4k(
                1604, y_start, 1614, y_end, white_skill_color, threshold=0.1
            )
            if not has_white_left:
                count = -1
        return count

    def check_is_pure_color_in_4k(self, x1, y1, x2, y2, color_range=None, threshold=0.9):
        skill_area_box = self.box_of_screen_scaled(3840, 2160, x1, y1, x2, y2)
        bar = skill_area_box.crop_frame(self.frame)
        if bar.size == 0:
            return False
        height, width, _ = bar.shape
        consecutive_matches = 0
        for i in range(height):
            row_pixels = bar[i]
            unique_colors, counts = np.unique(row_pixels, axis=0, return_counts=True)
            idx = np.argmax(counts)
            dominant_count = counts[idx]
            dominant_color = unique_colors[idx]
            is_valid_row = (dominant_count / width) >= threshold
            if is_valid_row and color_range:
                b, g, r = dominant_color
                if not (
                    color_range["r"][0] <= r <= color_range["r"][1]
                    and color_range["g"][0] <= g <= color_range["g"][1]
                    and color_range["b"][0] <= b <= color_range["b"][1]
                ):
                    is_valid_row = False
            if is_valid_row:
                consecutive_matches += 1
                if consecutive_matches >= 2:
                    return True
            else:
                consecutive_matches = 0
        return False

    # ---------------- 自动战斗 ----------------
    def auto_battle(self, start_sleep: float = None):
        """启动主循环"""
        end_time = None
        start_time = time.time()
        while True:
            if time.time() - start_time > 420:
                self.log_info("自动战斗超时")
                return False
            if end_time and time.time() - end_time > 15:
                self.log_info("战斗完成")
                return True
            battle_done = AutoCombatLogic(self).run(start_sleep=start_sleep)
            if not battle_done:
                self.sleep(0.1)
            else:
                end_time = time.time()

    def _exit_checker(self):
        """慢速退出检测线程"""
        while True:
            frame_copy = self.frame.copy()
            if self.is_combat_ended(frame_copy=frame_copy):
                self.log_info("退出检测线程: 战斗结束")
                break
            time.sleep(0.3)

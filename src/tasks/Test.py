from src.tasks.BaseEfTask import BaseEfTask
from src.tasks.AutoCombatTask import AutoCombatTask
from src.data.FeatureList import FeatureList as fL
import re
import time

class Test(BaseEfTask):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_config = {'_enabled': True}
        self.name = "测试"
        self.description = "完整战斗测试"
        self.default_config.update({
            "技能释放": "123",
            "启动技能点数": 2,
            "后台结束战斗通知": True,
            "无数字操作间隔": 6
        })
        self.lv_regex = re.compile(r"(?i)lv|\d{2}")
        self.last_op_time = 0
        self.last_skill_time = 0
        self.exit_check_count = 0  # 退出验证计数器，需要連续捐捕 2 次
        self._last_exit_fail_skill_count = None
        self.last_no_number_action_time = 0

    def test_times_ocr(self):
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
    def test_room_ocr(self):
        self.wait_click_ocr(match=[re.compile(i) for i in ["会客", "培养", "制造"]], time_out=5, after_sleep=2,log=True)

    def run(self):
        raw_skill_config = self.config.get("技能释放", "123")
        start_trigger_count = self.config.get("启动技能点数", 2)
        skill_sequence = self._parse_skill_sequence(raw_skill_config)

        while True:
            if not self.in_combat(required_yellow=1):
                self.sleep(0.1)
                continue

            self.log_info("进入战斗!", notify=True)

            if self.debug:
                self.screenshot('enter_combat')

            self.click(key='middle')

            while True:
                skill_count = self.get_skill_bar_count()

                # 使用新的退出检查方法
                if self.is_combat_ended():
                    if self.debug:
                        self.screenshot('out_of_combat')
                    self.log_info("退出战斗!", notify=True)
                    self.log_info("退出战斗主循环")
                    break

                self.handle_no_damage_number_actions()

                if self.use_e_skill() or self.use_ult():
                    continue

                if skill_count >= start_trigger_count:
                    self.log_info(f"Triggering sequence at {skill_count} points")

                    for skill_key in skill_sequence:
                        if not self.in_combat():
                            break

                        while True:
                            current_points = self.get_skill_bar_count()
                            time_since_last_skill = time.time() - self.last_skill_time

                            if current_points >= 1 and time_since_last_skill >= 1.0:
                                break

                            if self.use_e_skill() or self.use_ult():
                                continue

                            if current_points < 0 and (self.ocr_lv() or not self.in_team()):
                                break

                            self.handle_no_damage_number_actions()
                            self.perform_attack_weave()
                            self.sleep(0.05)

                        if not self.in_combat():
                            break

                        self.send_key(skill_key)
                        self.last_skill_time = time.time()
                        self.last_op_time = time.time()
                        self.log_info(f"Used skill {skill_key}")

                    self.log_info("Sequence finished, returning to charge mode")
                else:
                    self.perform_attack_weave()

                self.sleep(0.05)

    perform_attack_weave = AutoCombatTask.perform_attack_weave
    _parse_skill_sequence = AutoCombatTask._parse_skill_sequence
    use_ult = AutoCombatTask.use_ult
    wait_in_combat = AutoCombatTask.wait_in_combat
    is_combat_ended = AutoCombatTask.is_combat_ended
    _check_single_exit_condition = AutoCombatTask._check_single_exit_condition
    _check_center_area_has_number = AutoCombatTask._check_center_area_has_number
    handle_no_damage_number_actions = AutoCombatTask.handle_no_damage_number_actions
    use_e_skill = AutoCombatTask.use_e_skill
    ocr_lv = AutoCombatTask.ocr_lv
    in_combat = AutoCombatTask.in_combat
    in_team = AutoCombatTask.in_team
    get_skill_bar_count = AutoCombatTask.get_skill_bar_count
    check_is_pure_color_in_4k = AutoCombatTask.check_is_pure_color_in_4k

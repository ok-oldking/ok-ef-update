import threading
import time
from src.tasks.BaseEfTask import BaseEfTask


class AutoCombatLogic:
    def __init__(self, task: BaseEfTask):
        self.task = task

        # 控制战斗开始/结束
        self.in_combat_flag = threading.Event()
        self.stop_flag = threading.Event()

        # 控制技能初始等待
        self.skill_start_flag = threading.Event()

        # 锁
        self.frame_lock = threading.Lock()  # 截图线程写，其他线程读
        self.ocr_lock = threading.Lock()  # OCR 调用锁

        # 共享截图
        self.frame = None

    def run(self, start_sleep: float = None):
        task = self.task

        # 1️⃣ 等待战斗开始
        if not task.in_combat(required_yellow=1):
            return False
        self.in_combat_flag.set()
        task.log_info("检测到战斗开始，启动子线程")

        # 2️⃣ 启动线程
        threads = [
            threading.Thread(target=self._frame_updater, daemon=True),
            threading.Thread(target=self._auto_attack, daemon=True),
            threading.Thread(target=self._auto_dodge, daemon=True),
            threading.Thread(target=self._skill_handler, daemon=True),
            threading.Thread(target=self._exit_checker, daemon=True),
        ]
        for t in threads:
            t.start()

        # 3️⃣ 技能初始等待（只影响技能线程）
        if start_sleep is not None:
            task.sleep(start_sleep)
        else:
            task.sleep(task.config.get("进入战斗后的初始等待时间", 3))
        self.skill_start_flag.set()

        # 4️⃣ 等待战斗结束
        while not self.stop_flag.is_set():
            task.sleep(0.05)

        task.log_info("战斗主循环结束")
        return True

    # ----------------- 子线程 -----------------

    def _frame_updater(self):
        """截图线程：持续更新共享 frame"""
        task = self.task
        while not self.stop_flag.is_set():
            frame = task.next_frame()  # 获取最新截图
            with self.frame_lock:
                self.frame = frame
            time.sleep(0.016)  # 约 60 FPS

    def _auto_attack(self):
        """普攻线程：立即按住"""
        task = self.task
        self.in_combat_flag.wait()
        while not self.stop_flag.is_set():
            task.perform_attack_weave()
        task.log_info("普攻线程退出")

    def _auto_dodge(self):
        """闪避线程：持续执行向前闪避"""
        task = self.task
        self.in_combat_flag.wait()
        while not self.stop_flag.is_set():
            task.handle_no_damage_number_actions()
            time.sleep(task.config.get("无数字操作间隔", 6))
        task.log_info("闪避线程退出")

    def _skill_handler(self):
        """技能线程：受初始等待控制"""
        task = self.task
        self.in_combat_flag.wait()
        self.skill_start_flag.wait()

        raw_skill_config = task.config.get("技能释放", "123")
        skill_sequence = task._parse_skill_sequence(raw_skill_config)
        start_trigger_count = task.config.get("启动技能点数", 2)

        while not self.stop_flag.is_set():
            # 读取共享截图
            with self.frame_lock:
                frame_copy = self.frame.copy() if self.frame is not None else None

            skill_count = task.get_skill_bar_count(frame_copy=frame_copy)
            if skill_count >= start_trigger_count:
                for key in skill_sequence:
                    if not task.in_combat(frame_copy=frame_copy):
                        break
                    # OCR 调用加锁

                    task.send_key(key)
                    task.last_skill_time = time.time()
                    task.last_op_time = time.time()
                    task.log_info(f"技能线程：释放技能 {key}")
            else:
                task.perform_attack_weave()

            with self.ocr_lock:
                if task.use_link_skill(frame_copy=frame_copy) or task.use_ult(frame_copy=frame_copy):
                    continue
            time.sleep(0.02)

    def _exit_checker(self):
        """退出检查线程：周期慢检测战斗结束"""
        task = self.task
        self.in_combat_flag.wait()

        success_count = 0
        success_limit = 3

        fail_count = 0
        fail_limit = 3

        while not self.stop_flag.is_set():

            # 读取共享截图
            with self.frame_lock:
                frame_copy = self.frame.copy() if self.frame is not None else None

            # OCR 调用加锁
            with self.ocr_lock:
                ended = task.is_combat_ended(frame_copy=frame_copy)

            if ended:
                success_count += 1
                fail_count = 0
                task.log_debug(f"退出检查成功累计 {success_count}/{success_limit}")

            else:
                fail_count += 1
                task.log_debug(f"退出检查失败累计 {fail_count}/{fail_limit}")

                if fail_count >= fail_limit:
                    success_count = 0
                    fail_count = 0
                    task.log_debug("失败达到阈值，重置成功计数")

            if success_count >= success_limit:
                task.log_info("退出检查线程：确认战斗结束")
                self.stop_flag.set()
                break

            time.sleep(1)

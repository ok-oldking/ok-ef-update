"""自动战斗模块 - 从 AutoCombatTask 复用战斗逻辑"""
import time
from typing import TYPE_CHECKING, Callable

from src.tasks.AutoCombatTask import AutoCombatTask

if TYPE_CHECKING:
    from src.tasks.BaseEfTask import BaseEfTask


def auto_battle(task_instance: "BaseEfTask", config: dict = None,
                end_check: Callable[["BaseEfTask"], bool] | None = None) -> bool:
    """
    执行完整的自动战斗流程，持续监控并自动战斗直到退出。
    
    Args:
        task_instance: BaseEfTask 实例（通常是 DailyTask）
        config: 战斗配置字典，包含：
            - "技能释放": 技能序列字符串（如"123"）
            - "启动技能点数": 触发技能的点数阈值（1-3）
            - "后台结束战斗通知": 是否在后台时通知战斗结束
        end_check: 自定义结束判定函数，返回 True 表示应退出战斗
    
    Returns:
        bool: 战斗是否完成
    """
    if config is None:
        config = {
            "技能释放": "123",
            "启动技能点数": 2,
            "后台结束战斗通知": True,
            "平A间隔": 0.12,
            "无数字操作间隔": 6,
        }
    
    # 从 AutoCombatTask 复用方法
    in_combat = AutoCombatTask.in_combat.__get__(task_instance, type(task_instance))
    get_skill_bar_count = AutoCombatTask.get_skill_bar_count.__get__(task_instance, type(task_instance))
    ocr_lv = AutoCombatTask.ocr_lv.__get__(task_instance, type(task_instance))
    in_team = AutoCombatTask.in_team.__get__(task_instance, type(task_instance))
    use_link_skill = AutoCombatTask.use_link_skill.__get__(task_instance, type(task_instance))
    use_ult = AutoCombatTask.use_ult.__get__(task_instance, type(task_instance))
    perform_attack_weave = AutoCombatTask.perform_attack_weave.__get__(task_instance, type(task_instance))
    handle_no_damage_number_actions = AutoCombatTask.handle_no_damage_number_actions.__get__(task_instance, type(task_instance))
    _parse_skill_sequence = AutoCombatTask._parse_skill_sequence.__get__(task_instance, type(task_instance))
    is_combat_ended = AutoCombatTask.is_combat_ended.__get__(task_instance, type(task_instance))

    def _is_combat_ended() -> bool:
        if end_check is None:
            return is_combat_ended()
        try:
            return bool(end_check(task_instance))
        except TypeError:
            # 兼容无参回调
            return bool(end_check())
    
    # 检查是否在战斗中
    if not in_combat(required_yellow=1):
        return False
    
    task_instance.log_info("进入战斗!", notify=True)
    
    if task_instance.debug:
        task_instance.screenshot('auto_battle_enter')
    
    # 初始化状态
    task_instance.last_op_time = time.time()
    task_instance.last_skill_time = time.time()
    task_instance.exit_check_count = getattr(task_instance, "exit_check_count", 0)
    task_instance._last_exit_fail_skill_count = getattr(task_instance, "_last_exit_fail_skill_count", None)
    task_instance.last_no_number_action_time = getattr(task_instance, "last_no_number_action_time", 0)
    task_instance.config = {**getattr(task_instance, "config", {}), **config}
    task_instance.click(key='middle')
    
    raw_skill_config = config.get("技能释放", "123")
    start_trigger_count = config.get("启动技能点数", 2)
    skill_sequence = _parse_skill_sequence(raw_skill_config)
    
    # 战斗循环
    while True:
        skill_count = get_skill_bar_count()
        
        # 退出条件 - 使用改进的检查方法
        if _is_combat_ended():
            if task_instance.debug:
                task_instance.screenshot('auto_battle_exit')
            task_instance.log_info("退出战斗!", notify=True)
            return True

        handle_no_damage_number_actions()
        
        # 优先使用 E 技能或大招
        if use_link_skill() or use_ult():
            continue
        
        # 技能释放逻辑
        if skill_count >= start_trigger_count:
            task_instance.log_info(f"Triggering sequence at {skill_count} points")
            
            for skill_key in skill_sequence:
                if not in_combat():
                    break
                
                # 等待条件：足够的技能点 + 冷却时间
                while True:
                    current_points = get_skill_bar_count()
                    time_since_last_skill = time.time() - task_instance.last_skill_time
                    
                    if current_points >= 1 and time_since_last_skill >= 1.0:
                        break
                    
                    if use_link_skill() or use_ult():
                        continue
                    
                    if current_points < 0 and (ocr_lv() or not in_team()):
                        break

                    if _is_combat_ended():
                        break
                    
                    handle_no_damage_number_actions()
                    perform_attack_weave()
                    task_instance.sleep(0.005)
                
                if not in_combat():
                    break
                
                task_instance.send_key(skill_key)
                task_instance.last_skill_time = time.time()
                task_instance.last_op_time = time.time()
                task_instance.log_info(f"Used skill {skill_key}")
            
            task_instance.log_info("Sequence finished, returning to charge mode")
        else:
            # 充能阶段：普通攻击
            perform_attack_weave()
        
        task_instance.sleep(0.005)

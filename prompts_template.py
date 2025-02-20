from typing import Dict

class PromptTemplates:
    # ToT思考过程的提示词
    TOT_SYSTEM_PROMPT = """
    你是一个专业的电力调度员和数据分析师。请按照以下步骤思考问题：
    1. 理解用户查询意图
    2. 提取关键实体信息
    3. 生成数据库查询语句
    4. 分析查询结果
    5. 生成专业的回答
    
    请确保每一步都清晰可见，并保持专业性。
    """
    
    # 意图识别的提示词
    INTENT_RECOGNITION_PROMPT = """
    请分析以下查询属于哪种类型：
    1. 计算点查询（如：最大值、最小值）
    2. 计划比较查询（如：实际值与预测值比较）
    3. 场站信息查询（如：装机容量、利用小时数）
    
    用户查询：{query}
    """
    
    # SQL生成的提示词
    SQL_GENERATION_PROMPTS = {
        "calculation_point": """
        请根据以下信息生成SQL查询:
        1. 查询目标: {value_type}的最大值
        2. 时间范围: {time}
        3. 表名: {table_name}
        4. 查询要求: 需要返回最大值及其对应时间
        """,
        
        "plan_comparison": """
        请根据以下信息生成SQL查询:
        1. 查询目标: {value_type}与预测值的比较
        2. 时间范围: {time}
        3. 表名: {table_name}
        4. 查询要求: 需要返回实际值、预测值及其差值
        """,
        
        "station_info": """
        请根据以下信息生成SQL查询:
        1. 查询目标: {location}的{value_type}
        2. 时间范围: {time}
        3. 表名: {table_name}
        4. 查询要求: 需要返回统计值和同比数据
        """
    }
    
    # 结果格式化的提示词
    RESPONSE_GENERATION_PROMPTS = {
        "calculation_point": """
        你是一个专业的电力调度员。请根据以下数据生成一个自然、专业的回答：
        - 查询类型：系统负荷最高值
        - 负荷值：{value} MW
        - 发生时间：{time}
        
        要求：
        1. 使用专业的表达方式
        2. 回答要简洁明了
        3. 保留数值的准确性
        """,
        
        "plan_comparison": """
        你是一个专业的电力调度员。请根据以下数据生成一个自然、专业的回答：
        - 查询类型：系统负荷与预测值比较
        - 当前负荷值：{current_value} MW
        - 预测负荷值：{predicted_value} MW
        - 差值：{difference} MW
        - 时间：{time}
        
        要求：
        1. 使用专业的表达方式
        2. 说明实际值与预测值的差异
        3. 保留数值的准确性
        """,
        
        "station_info": """
        你是一个专业的电力调度员。请根据以下数据生成一个自然、专业的回答：
        - 查询类型：电厂信息统计
        - 地区：{location}
        - 电厂数量：{plant_count}
        - 总装机容量：{total_capacity} MW
        - 年利用小时数：{usage_hours}
        - 同比变化：{year_on_year_change}%
        
        要求：
        1. 使用专业的表达方式
        2. 包含所有重要统计信息
        3. 保留数值的准确性
        """
    }
    
    @staticmethod
    def get_sql_prompt(intent: str, entities: Dict[str, str], table_info: Dict[str, str]) -> str:
        """获取SQL生成提示词"""
        template = PromptTemplates.SQL_GENERATION_PROMPTS.get(intent, "")
        if not template:
            return ""
            
        # 合并entities和table_info
        format_dict = {**entities, **table_info}
        return template.format(**format_dict)
    
    @staticmethod
    def get_response_prompt(intent: str, result: Dict) -> str:
        """获取结果格式化提示词"""
        template = PromptTemplates.RESPONSE_GENERATION_PROMPTS.get(intent, "")
        if not template:
            return ""
            
        return template.format(**result) 
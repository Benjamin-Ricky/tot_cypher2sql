from typing import Dict

class PromptTemplates:
    # ToT思考过程的提示词
    TOT_SYSTEM_PROMPT = """你是一个专业的电力调度员，需要帮助查询电力系统数据。你必须严格按照步骤执行查询，每一步都需要进行数据库查询。"""
    
    # 意图识别的提示词
    INTENT_RECOGNITION_PROMPT = """
第1步 - 意图识别：
请分析查询属于以下哪种类型：
1. 计算点查询（如：最大值、最小值）- 需要查询历史采样保存表
2. 计划比较查询（如：实际值与预测值比较）- 需要查询历史采样保存表
3. 场站信息查询（如：装机容量、利用小时数）- 需要查询电厂信息表

问题: {query}

输出格式：
```json
{{
    "thought": "这是一个[具体类型]查询，需要查询[具体表名]",
    "value": 0.9,
    "proposed_thoughts": [
        "下一步需要确定具体的查询字段",
        "需要提取时间/地点等关键信息"
    ]
}}
```
"""

    # 实体提取和知识图谱查询的提示词
    ENTITY_EXTRACTION_PROMPT = """
第2步 - 实体提取和知识图谱查询：
请从问题中提取以下信息用于查询知识图谱：
1. 时间信息（如：今天、昨天、具体日期）
2. 值类型（如：系统负荷、装机容量）
3. 地点信息（如：广东省）
4. 电厂类型（如：煤电、燃气）

已知实体: {entities}
表信息: {table_info}

然后生成Neo4j查询语句，格式如下：
```json
{{
    "thought": "需要在知识图谱中查找[具体表名]和[具体字段]的关系",
    "value": 0.9,
    "proposed_thoughts": [
        "MATCH (t:Table)-[:CONTAINS]->(v:ValueType) WHERE...",
        "需要获取表名和字段名用于后续MySQL查询"
    ]
}}
```
"""

    # SQL生成的提示词
    SQL_GENERATION_PROMPT = """
第3步 - MySQL查询语句生成：
基于知识图谱查询结果，请生成具体的MySQL查询语句：
1. 使用正确的表名和字段名
2. 添加适当的时间条件
3. 根据查询类型添加聚合函数（如MAX、AVG等）

已知信息：
- 查询意图: {intent}
- 实体信息: {entities}
- 表信息: {table_info}

输出格式：
```json
{{
    "thought": "生成MySQL查询语句获取具体数据",
    "value": 0.9,
    "proposed_thoughts": [
        "SELECT [具体字段] FROM [表名] WHERE...",
        "需要考虑时间范围和其他过滤条件"
    ]
}}
```
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
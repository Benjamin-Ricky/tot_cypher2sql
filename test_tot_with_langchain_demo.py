from templates import problem_description
from typing import Tuple, List, Dict, Any
from langchain_ollama import OllamaLLM
from langchain_experimental.tot.checker import ToTChecker
from langchain_experimental.tot.thought import ThoughtValidity
from langchain_experimental.tot.base import ToTChain
from langchain_community.llms import Tongyi
import re
from database import Neo4jManager, MySQLManager
from prompts_template import PromptTemplates
from responses_template import ResponseTemplates
from pydantic import BaseModel, Field
import json

# 知识图谱中的存在的查询项集
valid = [] 

# 初始化 deepseek 模型
# 注意这边 ollama 服务要确认已经启动 (ollama serve)
llm = OllamaLLM(model="deepseek-r1:7b")


class QueryType:
    CALCULATION_POINT = "calculation_point"
    PLAN_COMPARISON = "plan_comparison"
    STATION_INFO = "station_info"

class IntentRecognizer:
    def __init__(self):
        self.intent_patterns = {
            QueryType.CALCULATION_POINT: [
                r".*系统负荷最高值.*",
                r".*系统最高负荷.*"
            ],
            QueryType.PLAN_COMPARISON: [
                r".*负荷比预测值.*",
                r".*比预测值.*"
            ],
            QueryType.STATION_INFO: [
                r".*装机容量.*",
                r".*利用小时数.*",
                r".*发电量.*"
            ]
        }
    
    def recognize(self, query: str) -> str:
        for intent_type, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.match(pattern, query):
                    return intent_type
        return None

class EntityExtractor:
    def __init__(self):
        self.time_pattern = r'(\d{4}-\d{2}-\d{2}|今天|昨天|本月|上月)'
        self.value_type_pattern = r'(负荷|发电量|装机容量|利用小时数)'
        self.location_pattern = r'([^省]+省|[^市]+市|[^区]+区)'
        self.plant_pattern = r'([^电厂]+电厂)'
        
    def extract(self, text: str) -> Dict[str, str]:
        entities = {
            'time': None,
            'value_type': None,
            'location': None,
            'plant': None
        }
        
        # 提取时间
        time_match = re.search(self.time_pattern, text)
        if time_match:
            entities['time'] = time_match.group(1)
            
        # 提取值类型
        value_match = re.search(self.value_type_pattern, text)
        if value_match:
            entities['value_type'] = value_match.group(1)
            
        # 提取地点
        location_match = re.search(self.location_pattern, text)
        if location_match:
            entities['location'] = location_match.group(1)
            
        # 提取电厂
        plant_match = re.search(self.plant_pattern, text)
        if plant_match:
            entities['plant'] = plant_match.group(1)
            
        return entities

class ThoughtSolverPrompt:
    def format(self, **kwargs) -> str:
        problem = kwargs.get("problem_description", "")
        thoughts = kwargs.get("thoughts", [])
        current_step = kwargs.get("current_step", 0)
        
        base_prompt = f"""你是一个专业的电力调度员，需要帮助查询电力系统数据。你必须严格按照以下步骤执行查询：

问题: {problem}

已有的思考:
{self._format_thoughts(thoughts)}

"""
        
        # 根据当前步骤生成不同的提示词
        if current_step == 0:
            prompt = base_prompt + """
第1步 - 意图识别：
请分析查询属于以下哪种类型：
1. 计算点查询（如：最大值、最小值）- 需要查询历史采样保存表
2. 计划比较查询（如：实际值与预测值比较）- 需要查询历史采样保存表
3. 场站信息查询（如：装机容量、利用小时数）- 需要查询电厂信息表

输出格式：
```json
{
    "thought": "这是一个[具体类型]查询，需要查询[具体表名]",
    "value": 0.9,
    "proposed_thoughts": [
        "下一步需要确定具体的查询字段",
        "需要提取时间/地点等关键信息"
    ]
}
```
"""

        elif current_step == 1:
            prompt = base_prompt + """
第2步 - 实体提取和知识图谱查询：
请从问题中提取以下信息用于查询知识图谱：
1. 时间信息（如：今天、昨天、具体日期）
2. 值类型（如：系统负荷、装机容量）
3. 地点信息（如：广东省）
4. 电厂类型（如：煤电、燃气）

然后生成Neo4j查询语句，格式如下：
```json
{
    "thought": "需要在知识图谱中查找[具体表名]和[具体字段]的关系",
    "value": 0.9,
    "proposed_thoughts": [
        "MATCH (t:Table)-[:CONTAINS]->(v:ValueType) WHERE...",
        "需要获取表名和字段名用于后续MySQL查询"
    ]
}
```
"""

        else:
            prompt = base_prompt + """
第3步 - MySQL查询语句生成：
基于知识图谱查询结果，请生成具体的MySQL查询语句：
1. 使用正确的表名和字段名
2. 添加适当的时间条件
3. 根据查询类型添加聚合函数（如MAX、AVG等）

输出格式：
```json
{
    "thought": "生成MySQL查询语句获取具体数据",
    "value": 0.9,
    "proposed_thoughts": [
        "SELECT [具体字段] FROM [表名] WHERE...",
        "需要考虑时间范围和其他过滤条件"
    ]
}
```
"""

        return prompt

    def _format_thoughts(self, thoughts: List[str]) -> str:
        if not thoughts:
            return "暂无已有思考"
        return "\n".join(f"- {t}" for t in thoughts)

class PowerDispatchChecker(ToTChecker, BaseModel):
    intent_recognizer: IntentRecognizer = Field(default_factory=IntentRecognizer)
    entity_extractor: EntityExtractor = Field(default_factory=EntityExtractor)
    neo4j_manager: Neo4jManager = Field(default_factory=Neo4jManager)
    mysql_manager: MySQLManager = Field(default_factory=MySQLManager)
    valid_entities: list = Field(default_factory=list)
    current_step: int = Field(default=0)
    max_steps: int = Field(default=3)
    current_query_info: Dict[str, Any] = Field(
        default_factory=lambda: {
            'intent': None,
            'entities': None,
            'table_info': None,
            'result': None
        }
    )
    prompts: PromptTemplates = Field(default_factory=PromptTemplates)
    response_templates: ResponseTemplates = Field(default_factory=ResponseTemplates)

    def __init__(self, **data):
        super().__init__(**data)
        self.valid_entities = self.neo4j_manager.get_valid_entities()

    def evaluate(self, problem_description: str, thoughts: Tuple[str, ...] = ()) -> ThoughtValidity:
        last_thought = thoughts[-1] if thoughts else ""
        
        try:
            # 解析大模型的输出
            if last_thought:
                try:
                    thought_json = json.loads(last_thought)
                    current_thought = thought_json.get("thought", "")
                except:
                    current_thought = last_thought
            else:
                current_thought = ""

            # Step 1: 意图识别
            if self.current_step == 0:
                intent = self.intent_recognizer.recognize(problem_description)
                if intent:
                    self.current_query_info['intent'] = intent
                    self.current_step += 1
                    return ThoughtValidity.VALID_INTERMEDIATE
                return ThoughtValidity.INVALID

            # Step 2: 实体提取和Neo4j查询
            elif self.current_step == 1:
                entities = self.entity_extractor.extract(problem_description)
                if entities:
                    self.current_query_info['entities'] = entities
                    
                    # 生成并执行Neo4j查询
                    cypher_info = self._generate_cypher_query(
                        self.current_query_info['intent'],
                        entities
                    )
                    
                    table_info = self.neo4j_manager.execute_query(
                        cypher_info["query"],
                        cypher_info["parameters"]
                    )
                    
                    if table_info:
                        self.current_query_info['table_info'] = table_info
                        self.current_step += 1
                        return ThoughtValidity.VALID_INTERMEDIATE
                return ThoughtValidity.INVALID

            # Step 3: 生成和执行SQL查询
            elif self.current_step == 2:
                sql_query = self._generate_sql_query(
                    self.current_query_info['intent'],
                    self.current_query_info['entities'],
                    self.current_query_info['table_info']
                )
                
                if sql_query:
                    result = self.mysql_manager.execute_query(sql_query)
                    if result:
                        self.current_query_info['result'] = result
                        self.current_step += 1
                        return ThoughtValidity.VALID_FINAL
                return ThoughtValidity.INVALID

        except Exception as e:
            print(f"Error in evaluate: {str(e)}")
            return ThoughtValidity.INVALID

        return ThoughtValidity.INVALID

    def _generate_sql_query(self, intent: str, entities: Dict[str, str], table_info: Dict[str, str]) -> str:
        """根据意图、实体和表信息生成SQL查询语句"""
        if intent == QueryType.CALCULATION_POINT:
            return f"""
            SELECT 时间, 系统负荷
            FROM yc_hs_720001cur_010
            WHERE 时间 >= '{entities['time']} 00:00:00'
            AND 时间 <= '{entities['time']} 23:59:59'
            ORDER BY 系统负荷 DESC
            LIMIT 1
            """
        
        elif intent == QueryType.PLAN_COMPARISON:
            return f"""
            SELECT 时间, 系统负荷 as actual_value, 系统负荷预测值 as predicted_value,
                   (系统负荷 - 系统负荷预测值) as difference
            FROM yc_hs_720001cur_010
            WHERE 时间 >= '{entities['time']} 00:00:00'
            AND 时间 <= '{entities['time']} 23:59:59'
            """
        
        elif intent == QueryType.STATION_INFO:
            return f"""
            SELECT *
            FROM power_plant_info
            WHERE 所在地区 = '{entities['location']}'
            AND 类型 = '{entities.get('plant_type', '煤电')}'
            """

    def _validate_entities(self, entities: Dict[str, str]) -> bool:
        # 验证提取的实体是否在知识图谱中存在
        for entity_value in entities.values():
            if entity_value and entity_value not in self.valid_entities:
                return False
        return True

    def _is_valid_query(self, thought: str) -> bool:
        # 验证生成的查询语句是否合法
        if "SELECT" not in thought.upper():
            return False
        if "FROM" not in thought.upper():
            return False
        # 可以添加更多的查询语句验证规则
        return True

    def format_result(self, result: List[Dict[str, Any]]) -> str:
        """格式化查询结果为自然语言"""
        if not result:
            return self.response_templates.ERROR_TEMPLATES["no_data"]
        
        try:
            intent = self.current_query_info['intent']
            
            if intent == QueryType.CALCULATION_POINT:
                return self.response_templates.format_load_response(
                    "max_load",
                    {
                        "time": result[0]["时间"].strftime("%Y年%m月%d日"),
                        "value": result[0]["系统负荷"],
                        "occurrence_time": result[0]["时间"].strftime("%H:%M"),
                        "trend_description": "呈现稳定上升趋势",
                        "factor_analysis": "主要受天气和用电需求影响"
                    }
                )
                
            elif intent == QueryType.PLAN_COMPARISON:
                return self.response_templates.format_load_response(
                    "load_comparison",
                    {
                        "time": result[0]["时间"].strftime("%Y年%m月%d日 %H:%M"),
                        "actual_value": result[0]["actual_value"],
                        "predicted_value": result[0]["predicted_value"],
                        "difference_description": f"{'低于' if result[0]['difference'] < 0 else '高于'}预测值{abs(result[0]['difference']):.2f} MW",
                        "deviation_rate": (result[0]['difference'] / result[0]['predicted_value']) * 100,
                        "deviation_reason": "天气变化导致用电需求变化",
                        "suggestion": "建议关注天气变化对负荷的影响"
                    }
                )
                
            elif intent == QueryType.STATION_INFO:
                return self.response_templates.format_plant_response(
                    "capacity_info",
                    {
                        "time": result[0]["时间"].strftime("%Y年%m月%d日"),
                        "location": result[0]["所在地区"],
                        "plant_type": result[0]["类型"],
                        "plant_count": len(result),
                        "total_capacity": sum(r["装机容量"] for r in result),
                        "usage_hours": sum(r["年利用小时数"] for r in result) / len(result),
                        "year_on_year_change": ((sum(r["年利用小时数"] for r in result) / len(result)) / 
                                              (sum(r["去年利用小时数"] for r in result) / len(result)) - 1) * 100,
                        "generation_percentage": 35.5  # 示例值，实际需要计算
                    }
                )
            
            return self.response_templates.ERROR_TEMPLATES["invalid_query"]
            
        except Exception as e:
            print(f"Error formatting result: {str(e)}")
            return self.response_templates.ERROR_TEMPLATES["system_error"]

    def _generate_cypher_query(self, intent: str, entities: Dict[str, str]) -> Dict[str, Dict[str, str]]:
        """根据意图和实体生成Cypher查询语句"""
        if intent == QueryType.CALCULATION_POINT:
            return {
                "query": """
                MATCH (t:Table)-[:CONTAINS]->(v:ValueType {name: $value_type})
                RETURN t.name as table_name, v.name as column_name
                """,
                "parameters": {"value_type": entities.get('value_type', '系统负荷')}
            }
            
        elif intent == QueryType.PLAN_COMPARISON:
            value_type = entities.get('value_type', '系统负荷')
            return {
                "query": """
                MATCH (t:Table)-[:CONTAINS]->(v:ValueType)
                WHERE v.name IN [$value_type, $predicted_type]
                RETURN t.name as table_name, v.name as column_name
                """,
                "parameters": {
                    "value_type": value_type,
                    "predicted_type": f"{value_type}预测值"
                }
            }
            
        elif intent == QueryType.STATION_INFO:
            return {
                "query": """
                MATCH (t:Table)-[:LOCATED_IN]->(l:Location {name: $location})
                RETURN t.name as table_name, l.name as location
                """,
                "parameters": {"location": entities.get('location')}
            }

def generate_prompt(query: str, intent: str, entities: Dict[str, str]) -> str:
    """生成提示词模板"""
    prompts = {
        QueryType.CALCULATION_POINT: """
        请根据以下信息生成SQL查询:
        1. 查询目标: {value_type}的最大值
        2. 时间范围: {time}
        3. 查询要求: 需要返回最大值及其对应时间
        """,
        QueryType.PLAN_COMPARISON: """
        请根据以下信息生成SQL查询:
        1. 查询目标: {value_type}与预测值的比较
        2. 时间范围: {time}
        3. 查询要求: 需要返回实际值、预测值及其差值
        """,
        QueryType.STATION_INFO: """
        请根据以下信息生成SQL查询:
        1. 查询目标: {location}的{value_type}
        2. 时间范围: {time}
        3. 查询要求: 需要返回统计值和同比数据
        """
    }
    
    return prompts[intent].format(**entities)

def generate_response_prompt(intent: str, result: Dict[str, Any]) -> str:
    prompts = {
        QueryType.CALCULATION_POINT: """
        你是一个专业的电力调度员。请根据以下数据生成一个自然、专业的回答：
        - 查询类型：系统负荷最高值
        - 负荷值：{value} MW
        - 发生时间：{time}
        
        要求：
        1. 使用专业的表达方式
        2. 回答要简洁明了
        3. 保留数值的准确性
        """,
        
        QueryType.PLAN_COMPARISON: """
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
        
        QueryType.STATION_INFO: """
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
    
    return prompts[intent].format(**result)

def main():
    llm = OllamaLLM(
        model="deepseek-r1:7b",
        system_prompt=PromptTemplates.TOT_SYSTEM_PROMPT
    )
    checker = PowerDispatchChecker()
    tot_chain = ToTChain(llm=llm, checker=checker, k=10, c=3, verbose=True)
    
    try:
        test_queries = [
            "今天系统负荷最高值是多少？",
            "今天系统负荷比预测值低多少？",
            "广东省内煤电装机容量是多少？"
        ]
        
        for query in test_queries:
            print(f"\n处理查询: {query}")
            result = tot_chain.run(problem_description=query)
            formatted_result = checker.format_result(checker.current_query_info['result'])
            print(f"查询结果: {formatted_result}")
            
    finally:
        checker.neo4j_manager.close()
        checker.mysql_manager.close()

if __name__ == "__main__":
    main()


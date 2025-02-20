from neo4j import GraphDatabase
import mysql.connector
from typing import Dict, List, Any
from config import NEO4J_CONFIG, MYSQL_CONFIG

def init_database():
    driver = GraphDatabase.driver(
        NEO4J_CONFIG['uri'],
        auth=(NEO4J_CONFIG['user'], NEO4J_CONFIG['password'])
    )
    
    # 使用system数据库来管理其他数据库
    with driver.session(database="system") as session:
        # 检查数据库是否存在
        result = session.run("""
            SHOW DATABASES 
            WHERE name = $db_name
        """, db_name="test_ToT")
        
        db_exists = result.single() is not None
        
        # 如果数据库不存在，创建它
        if not db_exists:
            try:
                session.run("CREATE DATABASE test_ToT")
                print("数据库 'test_ToT' 创建成功")
            except Exception as e:
                print(f"创建数据库时出错: {str(e)}")
                driver.close()
                return False
    
    driver.close()
    return True

class Neo4jManager:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            NEO4J_CONFIG['uri'],
            auth=(NEO4J_CONFIG['user'], NEO4J_CONFIG['password'])
        )
    
    def execute_query(self, query: str, parameters: dict = None) -> list:
        """执行Neo4j查询"""
        try:
            with self.driver.session(database="neo4j") as session:
                result = session.run(query, parameters or {})
                return [dict(record) for record in result]
        except Exception as e:
            print(f"Neo4j查询错误: {str(e)}")
            return []

    def get_valid_entities(self) -> list:
        """获取知识图谱中的有效实体"""
        query = """
        MATCH (n)
        WHERE n:Table OR n:ValueType OR n:Location OR n:PlantType
        RETURN n.name as name
        """
        try:
            with self.driver.session(database="neo4j") as session:
                result = session.run(query)
                return [record["name"] for record in result]
        except Exception as e:
            print(f"获取有效实体错误: {str(e)}")
            return []

    def close(self):
        """关闭数据库连接"""
        if self.driver:
            self.driver.close()

    def get_table_info(self, intent: str, entities: Dict[str, str]) -> Dict[str, str]:
        """获取查询所需的表格信息"""
        with self.driver.session(database="neo4j") as session:
            if intent == QueryType.CALCULATION_POINT:
                result = session.run("""
                    MATCH (t:Table)-[:CONTAINS]->(v:ValueType)
                    WHERE v.name = $value_type
                    RETURN t.name as table_name, v.name as column_name
                """, value_type=entities['value_type'])
                
            elif intent == QueryType.PLAN_COMPARISON:
                result = session.run("""
                    MATCH (t:Table)-[:CONTAINS]->(v:ValueType)
                    WHERE v.name = $value_type OR v.name = $value_type + '预测值'
                    RETURN t.name as table_name, v.name as column_name
                """, value_type=entities['value_type'])
                
            elif intent == QueryType.STATION_INFO:
                result = session.run("""
                    MATCH (t:Table)-[:LOCATED_IN]->(l:Location)
                    WHERE l.name = $location
                    RETURN t.name as table_name
                """, location=entities['location'])
            
            return result.single()

class MySQLManager:
    def __init__(self):
        self.connection = mysql.connector.connect(**MYSQL_CONFIG)
    
    def execute_query(self, query: str, parameters: tuple = None) -> list:
        """执行MySQL查询"""
        try:
            cursor = self.connection.cursor(dictionary=True)
            cursor.execute(query, parameters or ())
            result = cursor.fetchall()
            cursor.close()
            return result
        except Exception as e:
            print(f"MySQL查询错误: {str(e)}")
            return []

    def close(self):
        """关闭数据库连接"""
        if self.connection:
            self.connection.close()

class QueryBuilder:
    @staticmethod
    def build_calculation_point_query(table_info: Dict[str, str], entities: Dict[str, str]) -> str:
        return f"""
        SELECT 时间, {entities['value_type']}
        FROM {table_info['table_name']}
        WHERE {entities['value_type']} = (
            SELECT MAX({entities['value_type']})
            FROM {table_info['table_name']}
            WHERE 时间 BETWEEN '{entities['time']}' AND '{entities['time']}'
        )
        AND 时间 BETWEEN '{entities['time']}' AND '{entities['time']}'
        """
    
    @staticmethod
    def build_plan_comparison_query(table_info: Dict[str, str], entities: Dict[str, str]) -> str:
        return f"""
        SELECT a.时间, 
               a.{entities['value_type']} as actual_value,
               b.{entities['value_type']} as predicted_value,
               (a.{entities['value_type']} - b.{entities['value_type']}) as difference
        FROM {table_info['table_name']} a
        JOIN 预测值表 b ON a.时间 = b.时间
        WHERE a.时间 BETWEEN '{entities['time']}' AND '{entities['time']}'
        """
    
    @staticmethod
    def build_station_info_query(table_info: Dict[str, str], entities: Dict[str, str]) -> str:
        return f"""
        SELECT 时间, {entities['value_type']},
               LAG({entities['value_type']}, 1) OVER (ORDER BY 时间) as prev_value
        FROM {table_info['table_name']}
        WHERE 地区 = '{entities['location']}'
        AND 时间 BETWEEN '{entities['time']}' AND '{entities['time']}'
        """ 
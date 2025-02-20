from neo4j import GraphDatabase
import mysql.connector
from typing import Dict, List, Any
from config import NEO4J_CONFIG, MYSQL_CONFIG

class Neo4jManager:
    def __init__(self):
        self._driver = GraphDatabase.driver(
            NEO4J_CONFIG['uri'],
            auth=(NEO4J_CONFIG['user'], NEO4J_CONFIG['password'])
        )
        
    def close(self):
        self._driver.close()
        
    def get_valid_entities(self) -> set:
        with self._driver.session(database="test_ToT") as session:
            result = session.run("""
                MATCH (n)
                WHERE n:TimePoint OR n:ValueType OR n:Location OR n:Plant
                RETURN n.name as name
            """)
            return {record["name"] for record in result}
            
    def get_table_info(self, intent: str, entities: Dict[str, str]) -> Dict[str, str]:
        """获取查询所需的表格信息"""
        with self._driver.session(database="test_ToT") as session:
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
        self.conn = mysql.connector.connect(**MYSQL_CONFIG)
        
    def close(self):
        self.conn.close()
        
    def execute_query(self, sql: str) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor(dictionary=True)
        cursor.execute(sql)
        result = cursor.fetchall()
        cursor.close()
        return result

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
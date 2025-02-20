import mysql.connector
from config import MYSQL_CONFIG
from neo4j import GraphDatabase
from config import NEO4J_CONFIG
import time

def setup_mysql():
    # 修改配置以不指定数据库
    config = MYSQL_CONFIG.copy()
    if 'database' in config:
        del config['database']
    
    conn = mysql.connector.connect(**config)
    cursor = conn.cursor()
    
    # 创建数据库（如果不存在）
    cursor.execute("CREATE DATABASE IF NOT EXISTS test_ToT")
    cursor.execute("USE test_ToT")
    
    # 创建历史采样保存表（如果不存在）
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS yc_hs_720001cur_010 (
        id INT AUTO_INCREMENT PRIMARY KEY,
        时间 DATETIME,
        系统负荷 FLOAT,
        系统负荷预测值 FLOAT,
        分布式光伏出力 FLOAT,
        低压分布式光伏出力 FLOAT,
        低压分布式光伏预测值 FLOAT,
        地调负荷 FLOAT
    )
    """)
    
    # 创建电厂信息表（如果不存在）
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS power_plant_info (
        id INT AUTO_INCREMENT PRIMARY KEY,
        厂站名称 VARCHAR(100),
        类型 VARCHAR(50),
        装机容量 FLOAT,
        所在地区 VARCHAR(50),
        年利用小时数 FLOAT,
        去年利用小时数 FLOAT
    )
    """)
    
    # 检查表是否为空，只有在为空时才插入数据
    cursor.execute("SELECT COUNT(*) FROM yc_hs_720001cur_010")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO yc_hs_720001cur_010 (时间, 系统负荷, 系统负荷预测值, 分布式光伏出力, 低压分布式光伏出力)
        VALUES 
        ('2024-03-20 14:00:00', 55000, 54000, 3000, 1500),
        ('2024-03-20 14:15:00', 56000, 54500, 2800, 1400),
        ('2024-03-20 14:30:00', 57000, 55000, 2600, 1300)
        """)
    
    cursor.execute("SELECT COUNT(*) FROM power_plant_info")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO power_plant_info (厂站名称, 类型, 装机容量, 所在地区, 年利用小时数, 去年利用小时数)
        VALUES 
        ('广东A电厂', '煤电', 2000, '广东省', 4500, 4200),
        ('广东B电厂', '煤电', 1500, '广东省', 4300, 4100),
        ('广东C电厂', '燃气', 1000, '广东省', 3500, 3800)
        """)
    
    conn.commit()
    cursor.close()
    conn.close()

def setup_neo4j():
    driver = GraphDatabase.driver(
        NEO4J_CONFIG['uri'],
        auth=(NEO4J_CONFIG['user'], NEO4J_CONFIG['password'])
    )
    
    # 使用默认的 neo4j 数据库
    with driver.session(database="neo4j") as session:
        # 清理现有数据（可选）
        # session.run("MATCH (n) DETACH DELETE n")
        
        # 创建表节点
        session.run("""
        CREATE (t1:Table {name: 'yc_hs_720001cur_010', description: '历史采样保存表'})
        CREATE (t2:Table {name: 'power_plant_info', description: '电厂信息表'})
        """)
        
        # 创建值类型节点
        session.run("""
        CREATE (v1:ValueType {name: '系统负荷'})
        CREATE (v2:ValueType {name: '系统负荷预测值'})
        CREATE (v3:ValueType {name: '分布式光伏出力'})
        CREATE (v4:ValueType {name: '装机容量'})
        CREATE (v5:ValueType {name: '利用小时数'})
        CREATE (v6:ValueType {name: '发电量'})
        """)
        
        # 创建地区节点
        session.run("""
        CREATE (l1:Location {name: '广东省'})
        CREATE (l2:Location {name: '深圳市'})
        """)
        
        # 创建电厂类型节点
        session.run("""
        CREATE (pt1:PlantType {name: '煤电'})
        CREATE (pt2:PlantType {name: '燃气'})
        """)
        
        # 创建关系
        session.run("""
        MATCH (t:Table {name: 'yc_hs_720001cur_010'})
        MATCH (v:ValueType)
        WHERE v.name IN ['系统负荷', '系统负荷预测值', '分布式光伏出力']
        CREATE (t)-[:CONTAINS]->(v)
        """)
        
        session.run("""
        MATCH (t:Table {name: 'power_plant_info'})
        MATCH (v:ValueType)
        WHERE v.name IN ['装机容量', '利用小时数', '发电量']
        CREATE (t)-[:CONTAINS]->(v)
        """)
        
        session.run("""
        MATCH (t:Table {name: 'power_plant_info'})
        MATCH (l:Location)
        CREATE (t)-[:LOCATED_IN]->(l)
        """)
        
        session.run("""
        MATCH (t:Table {name: 'power_plant_info'})
        MATCH (pt:PlantType)
        CREATE (t)-[:HAS_TYPE]->(pt)
        """)
        
        print("Neo4j 知识图谱创建成功！")
    
    driver.close()

def main():
    print("设置Neo4j数据库...")
    setup_neo4j()
    print("设置MySQL数据库...")
    setup_mysql()
    print("数据库设置完成！")

if __name__ == "__main__":
    main() 
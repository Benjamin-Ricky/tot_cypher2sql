from typing import Dict

class ResponseTemplates:
    # 系统角色设定
    SYSTEM_ROLE = """
    你是一位经验丰富的电力调度专家，具有以下特点：
    1. 熟悉电力系统运行特性
    2. 精通电力负荷分析
    3. 了解发电厂运行指标
    4. 擅长数据分析和解读
    
    在回答问题时，请：
    1. 使用专业准确的术语
    2. 保持简洁清晰的表达
    3. 重点突出关键数据
    4. 必要时提供专业建议
    """
    
    # 错误响应模板
    ERROR_TEMPLATES = {
        "no_data": "抱歉，未能找到相关数据。",
        "invalid_query": "抱歉，查询格式不正确。",
        "system_error": "系统处理出现错误，请稍后重试。"
    }

    # 负荷查询响应模板
    LOAD_TEMPLATES = {
        "max_load": """
在{time}，系统最高负荷达到{value:.2f} MW，发生在{occurrence_time}。
负荷走势{trend_description}，{factor_analysis}。
""",
        "load_comparison": """
在{time}，系统实际负荷为{actual_value:.2f} MW，
{difference_description}，
偏差率为{deviation_rate:.2f}%。
原因分析：{deviation_reason}
建议：{suggestion}
"""
    }

    # 电厂信息响应模板
    PLANT_TEMPLATES = {
        "capacity_info": """
{location}{plant_type}电厂共{plant_count}家，
总装机容量达到{total_capacity:.2f} MW，
年利用小时数{usage_hours:.2f}小时，
同比{year_on_year_change:+.2f}%。
在该地区发电量占比{generation_percentage:.2f}%。
"""
    }
    
    # 负荷查询回答模板
    LOAD_QUERY_TEMPLATES = {
        # 系统负荷最高值
        "max_load": """
        根据调度数据显示，{time}系统最高负荷达到{value:.2f} MW，发生在{occurrence_time}。
        这一负荷水平{load_level_comment}。
        
        补充说明：
        - 负荷变化趋势：{trend_description}
        - 主要影响因素：{factor_analysis}
        """,
        
        # 负荷预测对比
        "load_comparison": """
        {time}时刻系统实际负荷为{actual_value:.2f} MW，
        对比预测负荷{predicted_value:.2f} MW，
        {difference_description}。
        
        具体分析：
        - 偏差率：{deviation_rate:.2f}%
        - 主要原因：{deviation_reason}
        - 建议措施：{suggestion}
        """
    }
    
    # 电厂信息回答模板
    PLANT_INFO_TEMPLATES = {
        # 装机容量查询
        "capacity_info": """
        截至{time}，{location}{plant_type}电厂共{plant_count}家，
        总装机容量达{total_capacity:.2f} MW。
        
        运行指标：
        - 年利用小时数：{usage_hours:.0f}小时
        - 同比{year_on_year_trend}：{year_on_year_change:.2f}%
        - 发电量占比：{generation_percentage:.2f}%
        """,
        
        # 利用小时数查询
        "usage_hours_info": """
        {time}{location}{plant_type}电厂平均利用小时数为{usage_hours:.0f}小时，
        同比{year_on_year_trend}{year_on_year_change:.2f}%。
        
        相关指标：
        - 设备利用率：{equipment_usage_rate:.2f}%
        - 发电能力：{generation_capacity:.2f} MW
        - 运行状态评价：{operation_status}
        """
    }
    
    @staticmethod
    def format_load_response(template_type: str, data: dict) -> str:
        """格式化负荷相关的响应"""
        template = ResponseTemplates.LOAD_TEMPLATES.get(template_type)
        if not template:
            return ResponseTemplates.ERROR_TEMPLATES["invalid_query"]
        return template.format(**data)

    @staticmethod
    def format_plant_response(template_type: str, data: dict) -> str:
        """格式化电厂信息相关的响应"""
        template = ResponseTemplates.PLANT_TEMPLATES.get(template_type)
        if not template:
            return ResponseTemplates.ERROR_TEMPLATES["invalid_query"]
        return template.format(**data)

    @staticmethod
    def format_load_response_old(template_type: str, data: Dict) -> str:
        """格式化负荷相关的回答"""
        template = ResponseTemplates.LOAD_QUERY_TEMPLATES.get(template_type)
        if not template:
            return ResponseTemplates.ERROR_TEMPLATES["invalid_query"]
            
        try:
            # 添加负荷水平评价逻辑
            if "value" in data:
                if data["value"] > 50000:
                    data["load_level_comment"] = "处于高负荷水平"
                elif data["value"] > 30000:
                    data["load_level_comment"] = "处于中等负荷水平"
                else:
                    data["load_level_comment"] = "处于低负荷水平"
            
            return template.format(**data)
        except KeyError:
            return ResponseTemplates.ERROR_TEMPLATES["no_data"]
        except Exception:
            return ResponseTemplates.ERROR_TEMPLATES["system_error"]
    
    @staticmethod
    def format_plant_response_old(template_type: str, data: Dict) -> str:
        """格式化电厂信息相关的回答"""
        template = ResponseTemplates.PLANT_INFO_TEMPLATES.get(template_type)
        if not template:
            return ResponseTemplates.ERROR_TEMPLATES["invalid_query"]
            
        try:
            # 添加同比趋势判断
            if "year_on_year_change" in data:
                data["year_on_year_trend"] = "增长" if data["year_on_year_change"] > 0 else "下降"
            
            return template.format(**data)
        except KeyError:
            return ResponseTemplates.ERROR_TEMPLATES["no_data"]
        except Exception:
            return ResponseTemplates.ERROR_TEMPLATES["system_error"] 
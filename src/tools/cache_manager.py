"""
缓存管理工具

用于管理validation和cross_validation阶段的缓存结果：
1. 按材料类型分类整理
2. 按优先级排序（高优先级错误在前）
3. 过滤通过的结果（仅显示警告和错误）
4. 生成结构化的报告数据
"""

from typing import Dict, List, Any, Optional
from collections import defaultdict


class ValidationCacheManager:
    """验证缓存管理器"""
    
    def __init__(self):
        self.priority_order = {
            "极高": 1,
            "高": 2,
            "中": 3,
            "低": 4
        }
        
        self.status_order = {
            "❌不通过": 1,
            "⚠️警告": 2,
            "✅通过": 3
        }
    
    def organize_validation_cache(self, validation_cache: List[Dict[str, Any]], 
                                cross_validation_cache: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        整理验证缓存数据
        
        Args:
            validation_cache: 材料验证缓存结果
            cross_validation_cache: 交叉验证缓存结果
            
        Returns:
            整理后的报告数据
        """
        print("📊 开始整理验证缓存数据...")
        
        # 按材料类型分类
        material_groups = self._group_by_material_type(validation_cache)
        
        # 添加交叉验证结果
        if cross_validation_cache:
            material_groups["交叉校验"] = cross_validation_cache
        
        # 过滤和排序每个材料类型的结果
        filtered_groups = {}
        total_issues = 0
        
        for material_type, results in material_groups.items():
            # 过滤掉通过的结果，只保留警告和错误
            filtered_results = self._filter_non_passing_results(results)
            
            if filtered_results:
                # 按优先级和状态排序
                sorted_results = self._sort_results_by_priority(filtered_results)
                filtered_groups[material_type] = sorted_results
                total_issues += len(sorted_results)
                
                print(f"  📋 {material_type}: {len(sorted_results)}个问题")
        
        # 生成统计信息
        statistics = self._generate_statistics(validation_cache, cross_validation_cache)
        
        print(f"✅ 缓存数据整理完成，共发现{total_issues}个需要关注的问题")
        
        return {
            "material_groups": filtered_groups,
            "statistics": statistics,
            "total_issues": total_issues,
            "processed_at": self._get_current_timestamp()
        }
    
    def _group_by_material_type(self, validation_cache: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """按材料类型分组"""
        groups = defaultdict(list)
        
        for result in validation_cache:
            material_type = result.get("material_type", "未知类型")
            groups[material_type].append(result)
        
        return dict(groups)
    
    def _filter_non_passing_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """过滤掉通过的结果，只保留警告和错误"""
        return [
            result for result in results 
            if result.get("result", "").strip() != "✅通过"
        ]
    
    def _sort_results_by_priority(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """按优先级和状态排序（高优先级、错误状态在前）"""
        def sort_key(result):
            priority = result.get("priority", "中")
            status = result.get("result", "⚠️警告")
            
            priority_score = self.priority_order.get(priority, 3)
            status_score = self.status_order.get(status, 2)
            
            return (priority_score, status_score)
        
        return sorted(results, key=sort_key)
    
    def _generate_statistics(self, validation_cache: List[Dict[str, Any]], 
                           cross_validation_cache: List[Dict[str, Any]]) -> Dict[str, Any]:
        """生成统计信息"""
        all_results = validation_cache + cross_validation_cache
        
        # 按状态统计
        status_counts = defaultdict(int)
        priority_counts = defaultdict(int)
        material_counts = defaultdict(int)
        
        for result in all_results:
            status = result.get("result", "⚠️警告")
            priority = result.get("priority", "中")
            material_type = result.get("material_type", "未知类型")
            
            status_counts[status] += 1
            priority_counts[priority] += 1
            material_counts[material_type] += 1
        
        return {
            "total_results": len(all_results),
            "validation_results": len(validation_cache),
            "cross_validation_results": len(cross_validation_cache),
            "status_distribution": dict(status_counts),
            "priority_distribution": dict(priority_counts),
            "material_distribution": dict(material_counts),
            "issues_count": len([r for r in all_results if r.get("result", "").strip() != "✅通过"])
        }
    
    def get_report_summary(self, organized_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成报告摘要
        
        Args:
            organized_data: 整理后的数据
            
        Returns:
            报告摘要信息
        """
        material_groups = organized_data.get("material_groups", {})
        statistics = organized_data.get("statistics", {})
        
        # 计算各类问题数量
        error_count = sum(
            len([r for r in results if r.get("result", "").startswith("❌")])
            for results in material_groups.values()
        )
        
        warning_count = sum(
            len([r for r in results if r.get("result", "").startswith("⚠️")])
            for results in material_groups.values()
        )
        
        # 最高优先级问题
        high_priority_issues = []
        for material_type, results in material_groups.items():
            for result in results:
                if result.get("priority") in ["极高", "高"]:
                    high_priority_issues.append({
                        "material_type": material_type,
                        "rule_name": result.get("rule_name", ""),
                        "details": result.get("details", ""),
                        "priority": result.get("priority", "")
                    })
        
        return {
            "total_materials_checked": len(statistics.get("material_distribution", {})),
            "total_issues": organized_data.get("total_issues", 0),
            "error_count": error_count,
            "warning_count": warning_count,
            "high_priority_count": len(high_priority_issues),
            "high_priority_issues": high_priority_issues[:5],  # 只显示前5个
            "material_issue_summary": {
                material_type: len(results) 
                for material_type, results in material_groups.items()
            }
        }
    
    def _get_current_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()


# 全局缓存管理器实例
cache_manager = ValidationCacheManager()


def organize_audit_cache(state) -> Dict[str, Any]:
    """
    整理审核缓存数据的便捷函数
    
    Args:
        state: 审核状态
        
    Returns:
        整理后的缓存数据
    """
    validation_cache = state.get("validation_cache", [])
    cross_validation_cache = state.get("cross_validation_cache", [])
    
    return cache_manager.organize_validation_cache(validation_cache, cross_validation_cache)


def get_report_data_from_cache(state) -> Dict[str, Any]:
    """
    从缓存中获取报告数据
    
    Args:
        state: 审核状态
        
    Returns:
        报告数据
    """
    organized_data = organize_audit_cache(state)
    summary = cache_manager.get_report_summary(organized_data)
    
    return {
        "organized_data": organized_data,
        "summary": summary,
        "cache_processed": True
    }
# -*- coding: utf-8 -*-
"""
韦恩图分析脚本 - 纯业务逻辑，不涉及UI
数据处理、统计分析、图表生成
"""

from script.utils_layer.import_config import os, tempfile, pd, itertools


class VennPlotAnalysis:
    """韦恩图分析类 - 纯业务逻辑"""

    def __init__(self):
        self.sets_data = {}
        self.intersection_results = {}
        self.temp_dir = os.path.join(tempfile.gettempdir(), 'koyuki_venn')
        os.makedirs(self.temp_dir, exist_ok=True)

    def read_table_data(self, table_widget):
        """从表格控件读取基因集合数据（只读取被表头勾选的列，未勾选列保留但不参与）"""
        sets_data = {}
        num_cols = table_widget.columnCount()

        if hasattr(table_widget, 'enabled_columns'):
            cols = table_widget.enabled_columns()
        else:
            cols = list(range(num_cols))

        for col in cols:
            if col >= num_cols:
                continue
            set_name_item = table_widget.item(0, col)
            set_name = set_name_item.text().strip() if set_name_item and set_name_item.text().strip() else f"集合{col+1}"

            genes = set()
            for row in range(1, table_widget.rowCount()):
                item = table_widget.item(row, col)
                if item and item.text().strip():
                    genes.add(item.text().strip())

            if genes:
                sets_data[set_name] = genes

        return sets_data

    def set_sets_data(self, sets_data):
        """设置集合数据"""
        self.sets_data = sets_data

    def calculate_intersections(self):
        """计算所有可能的交集"""
        self.intersection_results = {}
        set_names = list(self.sets_data.keys())
        num_sets = len(set_names)

        for r in range(2, num_sets + 1):
            for combo in itertools.combinations(set_names, r):
                combo_key = " ∩ ".join(combo)
                combo_genes = set.intersection(*[self.sets_data[name] for name in combo])
                self.intersection_results[combo_key] = combo_genes

        return self.intersection_results

    def get_intersection_results(self):
        """获取交集结果"""
        return self.intersection_results

    def draw_venn_diagram(self):
        """绘制韦恩图并保存到临时文件（同时保存PNG和PDF）"""
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            from venn import venn

            plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
            plt.rcParams['axes.unicode_minus'] = False

            num_sets = len(self.sets_data)
            if num_sets < 2:
                return None

            if num_sets <= 3:
                fig_size = (6, 6)
            elif num_sets <= 5:
                fig_size = (8, 8)
            else:
                fig_size = (10, 10)

            plt.figure(figsize=fig_size)
            ax = plt.gca()
            venn(self.sets_data, ax=ax)

            temp_path_png = os.path.join(self.temp_dir, 'venn_diagram.png')
            temp_path_pdf = os.path.join(self.temp_dir, 'venn_diagram.pdf')
            
            plt.savefig(temp_path_png, dpi=600, bbox_inches='tight')
            plt.savefig(temp_path_pdf, bbox_inches='tight')
            plt.close()

            return temp_path_png, temp_path_pdf

        except ImportError:
            return None, None
        except Exception:
            return None, None

    def get_intersection_matrix_data(self, intersection_results, sets_data):
        """获取交集矩阵数据（纯数据，不操作UI）"""
        set_names = list(sets_data.keys())
        num_sets = len(set_names)

        matrix_data = []
        header = [""] + set_names + ["总数"]

        for i in range(num_sets):
            row = [set_names[i]]
            for j in range(num_sets):
                if i == j:
                    gene_count = len(sets_data[set_names[i]])
                else:
                    combo = tuple(sorted([set_names[i], set_names[j]]))
                    combo_key = " ∩ ".join(combo)
                    if combo_key in intersection_results:
                        gene_count = len(intersection_results[combo_key])
                    else:
                        gene_count = len(set.intersection(sets_data[set_names[i]], sets_data[set_names[j]]))
                row.append(gene_count)
            row.append(len(sets_data[set_names[i]]))
            matrix_data.append(row)

        return header, matrix_data

    def export_gene_set_csv(self, sets_data, save_path):
        """导出基因集合为CSV"""
        max_len = max(len(genes) for genes in sets_data.values())

        data = {}
        for set_name, genes in sets_data.items():
            gene_list = list(genes)
            gene_list += [""] * (max_len - len(gene_list))
            data[set_name] = gene_list

        df = pd.DataFrame(data)
        df.to_csv(save_path, index=False, encoding='utf-8-sig')

    def build_intersection_gene_matrix(self, intersection_results):
        """构建“各交集基因”宽表：每列一个交集组合，列内自上而下为该交集的基因（对齐到最长列）"""
        combo_keys = sorted(intersection_results.keys())
        if not combo_keys:
            return [], []

        max_len = max(len(intersection_results[k]) for k in combo_keys)
        headers = [f"{k}（{len(intersection_results[k])}个基因）" for k in combo_keys]

        rows = []
        for i in range(max_len):
            row = []
            for k in combo_keys:
                genes = sorted(intersection_results[k])
                row.append(genes[i] if i < len(genes) else "")
            rows.append(row)
        return headers, rows

    def export_intersection_result_xlsx(self, intersection_results, sets_data, save_path):
        """导出交集结果为 xlsx（多sheet）：
        1) 交集矩阵统计：集合间两两交集的基因数
        2) 各交集基因明细：长表（交集组合、基因，每基因一行）
        3) 各交集基因宽表：每列一个交集组合，列出该交集内的全部基因
        """
        header, matrix_data = self.get_intersection_matrix_data(intersection_results, sets_data)
        stats_df = pd.DataFrame(matrix_data, columns=header)

        combo_keys = sorted(intersection_results.keys())
        detail_rows = []
        for k in combo_keys:
            for g in sorted(intersection_results[k]):
                detail_rows.append({'交集组合': k, '基因': g})
        detail_df = pd.DataFrame(detail_rows, columns=['交集组合', '基因'])

        max_len = max((len(intersection_results[k]) for k in combo_keys), default=0)
        wide_data = {}
        for k in combo_keys:
            genes = sorted(intersection_results[k])
            wide_data[k] = genes + [""] * (max_len - len(genes))
        wide_df = pd.DataFrame(wide_data)

        with pd.ExcelWriter(save_path, engine='openpyxl') as writer:
            stats_df.to_excel(writer, sheet_name='交集矩阵统计', index=False)
            detail_df.to_excel(writer, sheet_name='各交集基因明细', index=False)
            wide_df.to_excel(writer, sheet_name='各交集基因宽表', index=False)

    def export_intersection_matrix_csv(self, intersection_results, sets_data, save_path):
        """导出交集矩阵为CSV"""
        set_names = list(sets_data.keys())
        num_sets = len(set_names)

        rows = []
        header = [""] + set_names + ["总数"]

        for i in range(num_sets):
            row = [set_names[i]]
            for j in range(num_sets):
                if i == j:
                    gene_count = len(sets_data[set_names[i]])
                else:
                    combo = tuple(sorted([set_names[i], set_names[j]]))
                    combo_key = " ∩ ".join(combo)
                    if combo_key in intersection_results:
                        gene_count = len(intersection_results[combo_key])
                    else:
                        gene_count = len(set.intersection(sets_data[set_names[i]], sets_data[set_names[j]]))
                row.append(gene_count)
            row.append(len(sets_data[set_names[i]]))
            rows.append(row)

        df = pd.DataFrame(rows, columns=header)
        df.to_csv(save_path, index=False, encoding='utf-8-sig')

    def export_venn_pdf(self, pdf_path, save_path):
        """导出韦恩图为PDF（使用矢量图）"""
        import shutil
        if os.path.exists(pdf_path):
            shutil.copy(pdf_path, save_path)
            return True
        return False
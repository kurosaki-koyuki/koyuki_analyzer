# -*- coding: utf-8 -*-
"""
bulk Log-rank分析核心算法脚本 - Python版本
遍历所有基因进行生存分析，计算每个基因的log-rank检验p值和HR
"""

import pandas as pd
import numpy as np
import os


class BulkLogrankPyAnalysis:
    def __init__(self):
        self.adata = None
        self.result_df = None
        self.dataset_name = None
        self.dataset_output_dir = None

    def set_adata(self, adata):
        self.adata = adata

    def set_dataset_name(self, name):
        self.dataset_name = name

    def set_dataset_output_dir(self, output_dir):
        self.dataset_output_dir = output_dir

    def get_obs_columns(self):
        if self.adata is None:
            return []
        survival_cols = ['time', 'time (month)', 'state']
        valid_cols = []
        for col in self.adata.obs.columns:
            if col.strip() not in survival_cols:
                valid_cols.append(col)
        return valid_cols

    def get_obs_unique_values(self, column_name):
        if self.adata is None or column_name not in self.adata.obs.columns:
            return []
        unique_vals = self.adata.obs[column_name].unique()
        return sorted([str(v) for v in unique_vals if pd.notna(v)])

    def prepare_survival_data(self):
        """准备生存数据（时间和状态）"""
        adata = self.adata
        
        if 'time (month)' in adata.obs.columns:
            time_col = 'time (month)'
        elif 'time' in adata.obs.columns:
            time_col = 'time'
        else:
            return None, None
        
        if 'state' not in adata.obs.columns:
            return None, None
        
        time_data = pd.to_numeric(adata.obs[time_col].values, errors='coerce')
        state_data = pd.to_numeric(adata.obs['state'].values, errors='coerce')
        
        return time_data, state_data

    def run_logrank_analysis(self, group_col=None, pval_threshold=0.05, use_fdr=True,
                             filter_col='p_val',
                             filter1_col=None, filter1_groups=None,
                             filter2_col=None, filter2_groups=None):
        """
        执行log-rank分析，遍历所有基因
        :param group_col: 分组列名，如果为None则使用中位数分组
        :param pval_threshold: p值阈值
        :param use_fdr: 是否使用FDR校正
        :param filter_col: 过滤依据，'p_val'或'p_val_adj'
        """
        if self.adata is None:
            return None

        adata = self.adata
        results = []
        
        filtered_indices = adata.obs.index
        
        if filter1_col and filter1_groups and filter1_col in adata.obs.columns:
            filtered_indices = adata.obs[adata.obs[filter1_col].astype(str).isin(filter1_groups)].index
        
        if filter2_col and filter2_groups and filter2_col in adata.obs.columns:
            filtered_indices = adata.obs.loc[filtered_indices][adata.obs.loc[filtered_indices, filter2_col].astype(str).isin(filter2_groups)].index
        
        filtered_adata = adata[filtered_indices, :]
        
        total_samples = len(filtered_adata)
        
        if len(filtered_adata) < 10:
            return None
        
        if 'time (month)' in filtered_adata.obs.columns:
            time_col = 'time (month)'
        elif 'time' in filtered_adata.obs.columns:
            time_col = 'time'
        else:
            return None
        
        if 'state' not in filtered_adata.obs.columns:
            return None
        
        time_data = pd.to_numeric(filtered_adata.obs[time_col].values, errors='coerce')
        state_data = pd.to_numeric(filtered_adata.obs['state'].values, errors='coerce')
        
        gene_names = list(adata.var_names)
        total_genes = len(gene_names)
        
        skipped_small_sample = 0
        skipped_small_group = 0
        
        for idx, gene_name in enumerate(gene_names):
            if (idx + 1) % 100 == 0:
                print(f"Processing gene {idx+1}/{total_genes}...")
            
            try:
                gene_expr = filtered_adata[:, gene_name].X.flatten()
                
                df = pd.DataFrame({
                    'time': time_data,
                    'state': state_data,
                    'expression': gene_expr
                })
                
                df = df[df['time'].notna() & df['state'].notna() & df['expression'].notna()]
                df = df[df['time'] > 0]
                
                if len(df) < 10:
                    skipped_small_sample += 1
                    continue
                
                median_expr = df['expression'].median()
                high_idx = df['expression'] >= median_expr
                low_idx = df['expression'] < median_expr
                
                n_high = high_idx.sum()
                n_low = low_idx.sum()
                
                if n_high < 2 or n_low < 2:
                    skipped_small_group += 1
                    continue
                
                high_data = df[high_idx].copy()
                low_data = df[low_idx].copy()
                
                high_data['group'] = 'High'
                low_data['group'] = 'Low'
                
                p_value, hr = self.calculate_logrank_pvalue_and_hr(high_data, low_data)
                
                if p_value is None:
                    continue
                
                median_high = high_data['time'].median() if len(high_data) > 0 else np.nan
                median_low = low_data['time'].median() if len(low_data) > 0 else np.nan
                
                results.append({
                    'gene': gene_name,
                    'median_high': median_high,
                    'median_low': median_low,
                    'HR': hr,
                    'p_val': p_value,
                    'p_val_adj': np.nan,
                    'prognosis': 'not_significant',
                    'n_high': n_high,
                    'n_low': n_low
                })
                
            except Exception as e:
                continue
        
        if not results:
            return None
        
        self.result_df = pd.DataFrame(results)
        self.result_df['total_samples'] = total_samples
        
        if use_fdr and len(self.result_df) > 0:
            from statsmodels.stats.multitest import multipletests
            _, p_adj, _, _ = multipletests(self.result_df['p_val'].values, alpha=0.05, method='fdr_bh')
            self.result_df['p_val_adj'] = p_adj
        
        for idx in self.result_df.index:
            p_value_to_check = self.result_df.loc[idx, filter_col]
            if pd.notna(p_value_to_check) and p_value_to_check <= pval_threshold:
                if self.result_df.loc[idx, 'HR'] < 1:
                    self.result_df.loc[idx, 'prognosis'] = 'favorable'
                else:
                    self.result_df.loc[idx, 'prognosis'] = 'unfavorable'
            else:
                self.result_df.loc[idx, 'prognosis'] = 'not_significant'
        
        self.result_df = self.result_df.sort_values('p_val', ascending=True)
        
        return self.result_df

    def calculate_logrank_pvalue_and_hr(self, high_data, low_data):
        """计算log-rank检验的p值和HR"""
        from lifelines.statistics import logrank_test
        from lifelines import CoxPHFitter
        
        try:
            results = logrank_test(
                high_data['time'].values, low_data['time'].values,
                event_observed_A=high_data['state'].values,
                event_observed_B=low_data['state'].values
            )
            p_value = results.p_value
            
            try:
                df_cox = pd.concat([high_data, low_data], ignore_index=True)
                df_cox['group_num'] = df_cox['group'].map({'High': 1, 'Low': 0})
                
                cph = CoxPHFitter()
                cph.fit(df_cox, duration_col='time', event_col='state', formula='group_num')
                hr = np.exp(cph.params_['group_num'])
            except Exception:
                hr = np.nan
            
            return p_value, hr
            
        except Exception:
            return None, None

    def export_to_excel(self, file_path):
        if self.result_df is None:
            return
        
        favorable_df = self.result_df[self.result_df['prognosis'] == 'favorable'].copy()
        unfavorable_df = self.result_df[self.result_df['prognosis'] == 'unfavorable'].copy()
        
        with pd.ExcelWriter(file_path) as writer:
            self.result_df.to_excel(writer, sheet_name='总体列表', index=False)
            favorable_df.to_excel(writer, sheet_name='良好预后', index=False)
            unfavorable_df.to_excel(writer, sheet_name='不良预后', index=False)
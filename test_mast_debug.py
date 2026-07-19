import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import scanpy as sc
import pandas as pd
import numpy as np

from script.analyzer_layer.scRNAseq_layer.diff_layer.py_diff.diff_analysis import DiffAnalysis

def test_mast_diff_analysis():
    adata = sc.read('a:/PYidea/koyuki_analyzer/test_files/koyuki_beta2.5test/appdata/main/GSE117891_count.h5ad')
    
    print(f"Original shape: {adata.shape}")
    print(f"CellType unique: {adata.obs['CellType'].unique()}")
    print(f"SampleType unique: {adata.obs['SampleType'].unique()}")
    
    tumor_mask = adata.obs['CellType'] == 'Tumor'
    adata = adata[tumor_mask].copy()
    print(f"After Tumor filter shape: {adata.shape}")
    
    peritumoral_cells = adata.obs[adata.obs['SampleType'] == 'Peritumoral'].index.tolist()
    tumoral_cells = adata.obs[adata.obs['SampleType'] == 'Tumoral'].index.tolist()
    
    print(f"Peritumoral cells: {len(peritumoral_cells)}")
    print(f"Tumoral cells: {len(tumoral_cells)}")
    
    analysis = DiffAnalysis()
    analysis.set_adata(adata)
    
    filter_mask = pd.Series([True] * len(adata), index=adata.obs.index)
    
    try:
        results = analysis.run_diff_analysis(
            group_col='SampleType',
            selected_groups=[['Peritumoral'], ['Tumoral']],
            method='mannwhitney',
            min_cells=3,
            min_expr=0,
            use_fdr=True,
            pval_threshold=0.05,
            logfc_threshold=0.25,
            pct_threshold=0.1,
            filter_mask=filter_mask
        )
        print(f"Analysis completed successfully!")
        print(f"Results shape: {results.shape}")
        print(f"Significant genes (FDR<0.05): {sum(results['p_val_adj'] < 0.05)}")
        print(results.head())
    except Exception as e:
        import traceback
        print(f"Analysis failed: {e}")
        traceback.print_exc()

if __name__ == '__main__':
    test_mast_diff_analysis()
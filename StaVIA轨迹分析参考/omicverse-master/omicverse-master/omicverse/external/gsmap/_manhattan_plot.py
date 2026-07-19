from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from pandas.api.types import is_numeric_dtype

SUGGESTIVE_LINE_LABEL = "suggestive line"
GENOMEWIDE_LINE_LABEL = "genomewide line"


def _get_hover_text(dataframe, snpname=None, genename=None, annotationname=None):
    hover_text = ""
    if snpname is not None and snpname in dataframe.columns:
        hover_text = "SNP: " + dataframe[snpname].astype(str)
    if genename is not None and genename in dataframe.columns:
        hover_text = hover_text + "<br>GENE: " + dataframe[genename].astype(str)
    if annotationname is not None and annotationname in dataframe.columns:
        hover_text = hover_text + "<br>" + dataframe[annotationname].astype(str)
    return hover_text


def manhattan_plot(
    dataframe,
    chrm="CHR",
    bp="BP",
    p="P",
    snp="SNP",
    gene="GENE",
    annotation=None,
    logp=True,
    title="Manhattan Plot",
    showgrid=True,
    xlabel=None,
    ylabel="-log10(p)",
    point_size=5,
    showlegend=True,
    col=None,
    suggestiveline_value=-np.log10(1e-8),
    suggestiveline_color="#636efa",
    suggestiveline_width=1,
    genomewideline_value=-np.log10(5e-8),
    genomewideline_color="#EF553B",
    genomewideline_width=1,
    highlight=True,
    highlight_color="red",
    highlight_gene_list=None,
):
    """Create a plotly Manhattan plot from a GWAS dataframe."""

    plot = _manhattan_plot(
        dataframe,
        chrm=chrm,
        bp=bp,
        p=p,
        snp=snp,
        gene=gene,
        annotation=annotation,
        logp=logp,
    )
    return plot.figure(
        title=title,
        showgrid=showgrid,
        xlabel=xlabel,
        ylabel=ylabel,
        point_size=point_size,
        showlegend=showlegend,
        col=col,
        suggestiveline_value=suggestiveline_value,
        suggestiveline_color=suggestiveline_color,
        suggestiveline_width=suggestiveline_width,
        genomewideline_value=genomewideline_value,
        genomewideline_color=genomewideline_color,
        genomewideline_width=genomewideline_width,
        highlight=highlight,
        highlight_color=highlight_color,
        highlight_gene_list=highlight_gene_list,
    )


class _manhattan_plot:
    def __init__(
        self,
        dataframe,
        chrm="CHR",
        bp="BP",
        p="P",
        snp="SNP",
        gene="GENE",
        annotation=None,
        logp=True,
    ):
        if chrm not in dataframe.columns:
            raise KeyError(f"Column {chrm} not found in dataframe")
        if bp not in dataframe.columns:
            raise KeyError(f"Column {bp} not found in dataframe")
        if p not in dataframe.columns:
            raise KeyError(f"Column {p} not found in dataframe")
        if not is_numeric_dtype(dataframe[chrm].dtype):
            raise TypeError(f"Column {chrm} must be numeric")
        if not is_numeric_dtype(dataframe[bp].dtype):
            raise TypeError(f"Column {bp} must be numeric")
        if not is_numeric_dtype(dataframe[p].dtype):
            raise TypeError(f"Column {p} must be numeric")

        self.dataframe = dataframe.copy()
        self.chrm = chrm
        self.bp = bp
        self.p = p
        self.snp = snp
        self.gene = gene
        self.annotation = annotation
        self.logp = logp

        if logp:
            if (self.dataframe[p] <= 0).any():
                warnings.warn("P-values <= 0 found; clipping for log scale.", stacklevel=2)
                self.dataframe[p] = self.dataframe[p].clip(lower=1e-300)
            self.dataframe["__plot_value__"] = -np.log10(self.dataframe[p])
        else:
            self.dataframe["__plot_value__"] = self.dataframe[p]

        self.dataframe = self.dataframe.sort_values([self.chrm, self.bp]).reset_index(drop=True)
        self.dataframe["__ind__"] = range(len(self.dataframe))
        self.dataframe["__hover_text__"] = _get_hover_text(
            self.dataframe,
            snpname=self.snp,
            genename=self.gene,
            annotationname=self.annotation,
        )

    def figure(
        self,
        title="Manhattan Plot",
        showgrid=True,
        xlabel=None,
        ylabel="-log10(p)",
        point_size=5,
        showlegend=True,
        col=None,
        suggestiveline_value=None,
        suggestiveline_color="#636efa",
        suggestiveline_width=1,
        genomewideline_value=None,
        genomewideline_color="#EF553B",
        genomewideline_width=1,
        highlight=True,
        highlight_color="red",
        highlight_gene_list=None,
    ):
        figure = go.Figure()
        colors = [col or "#636efa", "#EF553B"]

        for chrom_index, chrom_value in enumerate(sorted(self.dataframe[self.chrm].unique())):
            chrom_df = self.dataframe[self.dataframe[self.chrm] == chrom_value]
            figure.add_trace(
                go.Scattergl(
                    x=chrom_df["__ind__"],
                    y=chrom_df["__plot_value__"],
                    mode="markers",
                    marker=dict(color=colors[chrom_index % len(colors)], size=point_size),
                    name=str(chrom_value),
                    text=chrom_df["__hover_text__"],
                    hovertemplate="%{text}<br>Value=%{y}<extra></extra>",
                )
            )

        if highlight and highlight_gene_list:
            highlight_mask = self.dataframe[self.gene].isin(highlight_gene_list)
            highlight_df = self.dataframe[highlight_mask]
            if not highlight_df.empty:
                figure.add_trace(
                    go.Scattergl(
                        x=highlight_df["__ind__"],
                        y=highlight_df["__plot_value__"],
                        mode="markers",
                        marker=dict(color=highlight_color, size=point_size + 2),
                        name="highlighted genes",
                        text=highlight_df["__hover_text__"],
                        hovertemplate="%{text}<br>Value=%{y}<extra></extra>",
                    )
                )

        if suggestiveline_value is not None:
            figure.add_hline(
                y=suggestiveline_value,
                line_color=suggestiveline_color,
                line_width=suggestiveline_width,
                annotation_text=SUGGESTIVE_LINE_LABEL,
            )
        if genomewideline_value is not None:
            figure.add_hline(
                y=genomewideline_value,
                line_color=genomewideline_color,
                line_width=genomewideline_width,
                annotation_text=GENOMEWIDE_LINE_LABEL,
            )

        if xlabel is None:
            xlabel = "Chromosome"

        tick_positions = self.dataframe.groupby(self.chrm)["__ind__"].median()
        figure.update_layout(
            title=title,
            xaxis_title=xlabel,
            yaxis_title=ylabel,
            showlegend=showlegend,
            xaxis=dict(
                tickmode="array",
                tickvals=tick_positions.to_list(),
                ticktext=[str(value) for value in tick_positions.index],
                showgrid=showgrid,
            ),
            yaxis=dict(showgrid=showgrid),
            template="plotly_white",
        )
        return figure

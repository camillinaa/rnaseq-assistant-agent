def create_plot(self, plot_type: str, **kwargs) -> Dict[str, Any]:
    """Create various types of plots from stored query data"""
    try:
        if not self.last_query_data or not self.last_query_data["data"]:
            return {"error": "No data available for plotting. Please run a SQL query first."}

        data = self.last_query_data["data"]
        df = pd.DataFrame(data)

        plot_type = plot_type.lower()

        if plot_type == "volcano":
            return self._volcano_plot(df, **kwargs)
        elif plot_type == "ma":
            return self._ma_plot(df, **kwargs)
        elif plot_type == "histogram":
            return self._histogram(df, **kwargs)
        elif plot_type == "scatter":
            return self._scatter_plot(df, **kwargs)
        elif plot_type == "boxplot":
            return self._box_plot(df, **kwargs)
        elif plot_type == "heatmap":
            return self._heatmap(df, **kwargs)
        elif plot_type == "bar":
            return self._bar_plot(df, **kwargs)
        elif plot_type == "pathway_enrichment":
            return self._pathway_enrichment_plot(df, **kwargs)
        else:
            return {"error": f"Plot type '{plot_type}' not supported. Available: volcano, ma, histogram, scatter, boxplot, heatmap, bar, pathway_enrichment"}

    except Exception as e:
        return {"error": f"Plot creation failed: {str(e)}"}


def _volcano_plot(self, df: pd.DataFrame, **kwargs) -> Dict[str, Any]:
    """Create interactive volcano plot"""
    try:
        # Auto-detect column names or use provided ones
        x_col = kwargs.get('x_column') or self._find_column(df, ['log2fc', 'log2foldchange', 'logfc'])
        y_col = kwargs.get('y_column') or self._find_column(df, ['padj', 'pvalue', 'p_adj'])

        if not x_col or not y_col:
            return {"error": f"Could not find required columns. Available: {list(df.columns)}"}

        # Calculate -log10(padj)
        df['neg_log10_padj'] = -np.log10(df[y_col].replace(0, 1e-300))

        # Add significance categories
        df['significance'] = 'Not significant'
        padj_thresh = kwargs.get('padj_threshold', 0.05)
        fc_thresh = kwargs.get('fc_threshold', 1)

        df.loc[(df[y_col] < padj_thresh) & (df[x_col] > fc_thresh), 'significance'] = 'Upregulated'
        df.loc[(df[y_col] < padj_thresh) & (df[x_col] < -fc_thresh), 'significance'] = 'Downregulated'

        # Create plot
        fig = px.scatter(
            df,
            x=x_col,
            y='neg_log10_padj',
            color='significance',
            color_discrete_map={
                'Upregulated': 'red',
                'Downregulated': 'blue',
                'Not significant': 'gray'
            },
            hover_data=['gene_id'] if 'gene_id' in df.columns else None,
            title='Volcano Plot - Differential Expression',
            labels={
                x_col: 'log2 Fold Change',
                'neg_log10_padj': '-log10(adjusted p-value)'
            }
        )

        # Add threshold lines
        fig.add_hline(y=-np.log10(padj_thresh), line_dash="dash", line_color="black", opacity=0.5)
        fig.add_vline(x=fc_thresh, line_dash="dash", line_color="black", opacity=0.5)
        fig.add_vline(x=-fc_thresh, line_dash="dash", line_color="black", opacity=0.5)

        filename = f"{self.output_dir}/volcano_plot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        fig.write_html(filename)

        # Count significant genes
        sig_up = len(df[df['significance'] == 'Upregulated'])
        sig_down = len(df[df['significance'] == 'Downregulated'])

        return {
            "success": True,
            "plot_path": filename,
            "plot_type": "volcano",
            "summary": f"Created volcano plot with {sig_up} upregulated and {sig_down} downregulated genes (padj < {padj_thresh}, |log2FC| > {fc_thresh})"
        }

    except Exception as e:
        return {"error": f"Volcano plot creation failed: {str(e)}"}

def _pathway_enrichment_plot(self, df: pd.DataFrame, **kwargs) -> Dict[str, Any]:
    """Create pathway enrichment bar plot"""
    try:
        pathway_col = kwargs.get('pathway_column') or self._find_column(df, ['ID', 'Description'])
        value_col = kwargs.get('value_column') or self._find_column(df, ['RichFactor', 'FoldEnrichment', 'zScore'])
        pval_col = kwargs.get('pval_column') or self._find_column(df, ['pvalue', 'p.adjust', 'qvalue'])

        if not pathway_col or not value_col:
            return {"error": f"Required columns not found. Available: {list(df.columns)}"}

        # Sort by significance and take top N
        top_n = kwargs.get('top_n', 20)
        if pval_col:
            df_plot = df.nsmallest(top_n, pval_col)
        else:
            df_plot = df.nlargest(top_n, value_col)

        # Create horizontal bar plot
        fig = px.bar(
            df_plot.iloc[::-1],  # Reverse for better visualization
            x=value_col,
            y=pathway_col,
            color=pval_col if pval_col else value_col,
            color_continuous_scale='viridis_r',
            title='Pathway Enrichment Analysis',
            labels={
                value_col: 'Fold Enrichment',
                pathway_col: 'Pathway'
            }
        )

        fig.update_layout(height=max(400, len(df_plot) * 25))

        filename = f"{self.output_dir}/pathway_enrichment_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        fig.write_html(filename)

        return {
            "success": True,
            "plot_path": filename,
            "plot_type": "pathway_enrichment",
            "summary": f"Created pathway enrichment plot with top {len(df_plot)} pathways"
        }

    except Exception as e:
        return {"error": f"Pathway enrichment plot failed: {str(e)}"}

def _ma_plot(self, df: pd.DataFrame, **kwargs) -> Dict[str, Any]:
    """Create MA plot (M vs A plot)"""
    try:
        fc_col = kwargs.get('fc_column') or self._find_column(df, ['log2fc', 'log2foldchange'])
        mean_col = kwargs.get('mean_column') or self._find_column(df, ['basemean', 'mean_expression', 'avg_expr'])

        if not fc_col or not mean_col:
            return {"error": f"Required columns not found. Need fold change and mean expression columns."}

        # Transform mean to log scale
        df['log_mean'] = np.log10(df[mean_col] + 1)

        fig = px.scatter(
            df,
            x='log_mean',
            y=fc_col,
            title='MA Plot',
            labels={
                'log_mean': 'log10(Mean Expression)',
                fc_col: 'log2 Fold Change'
            }
        )

        fig.add_hline(y=0, line_dash="dash", line_color="black")

        filename = f"{self.output_dir}/ma_plot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        fig.write_html(filename)

        return {
            "success": True,
            "plot_path": filename,
            "plot_type": "ma_plot",
            "summary": "Created MA plot showing relationship between expression level and fold change"
        }

    except Exception as e:
        return {"error": f"MA plot creation failed: {str(e)}"}

def _histogram(self, df: pd.DataFrame, **kwargs) -> Dict[str, Any]:
    """Create histogram"""
    try:
        column = kwargs.get('column')
        if not column or column not in df.columns:
            # Auto-select first numeric column
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            if len(numeric_cols) == 0:
                return {"error": "No numeric columns found for histogram"}
            column = numeric_cols[0]

        fig = px.histogram(
            df,
            x=column,
            nbins=kwargs.get('bins', 30),
            title=f'Histogram of {column}'
        )

        filename = f"{self.output_dir}/histogram_{column}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        fig.write_html(filename)

        return {
            "success": True,
            "plot_path": filename,
            "plot_type": "histogram",
            "summary": f"Created histogram showing frequency distribution of values in column '{column}'"
        }

    except Exception as e:
        return {"error": f"Histogram creation failed: {str(e)}"}

def _scatter_plot(self, df: pd.DataFrame, **kwargs) -> Dict[str, Any]:
    """Create scatter plot"""
    try:
        x_col = kwargs.get('x_column')
        y_col = kwargs.get('y_column')
        
        # Auto-select columns if not provided
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if not x_col and len(numeric_cols) > 0:
            x_col = numeric_cols[0]
        if not y_col and len(numeric_cols) > 1:
            y_col = numeric_cols[1]
        elif not y_col and len(numeric_cols) > 0:
            y_col = numeric_cols[0]

        if not x_col or not y_col:
            return {"error": "Need at least one numeric column for scatter plot"}

        fig = px.scatter(
            df,
            x=x_col,
            y=y_col,
            title=f'Scatter Plot: {x_col} vs {y_col}'
        )

        filename = f"{self.output_dir}/scatter_{x_col}_{y_col}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        fig.write_html(filename)

        return {
            "success": True,
            "plot_path": filename,
            "plot_type": "scatter",
            "summary": f"Created scatter plot showing relationship between {x_col} and {y_col}"
        }

    except Exception as e:
        return {"error": f"Scatter plot creation failed: {str(e)}"}

def _box_plot(self, df: pd.DataFrame, **kwargs) -> Dict[str, Any]:
    """Create box plot"""
    try:
        column = kwargs.get('column')
        if not column:
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            if len(numeric_cols) == 0:
                return {"error": "No numeric columns found for box plot"}
            column = numeric_cols[0]

        fig = px.box(
            df,
            y=column,
            title=f'Box Plot of {column}'
        )

        filename = f"{self.output_dir}/boxplot_{column}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        fig.write_html(filename)

        return {
            "success": True,
            "plot_path": filename,
            "plot_type": "boxplot",
            "summary": f"Created box plot showing distribution of {column}"
        }

    except Exception as e:
        return {"error": f"Box plot creation failed: {str(e)}"}

def _bar_plot(self, df: pd.DataFrame, **kwargs) -> Dict[str, Any]:
    """Create bar plot"""
    try:
        x_col = kwargs.get('x_column')
        y_col = kwargs.get('y_column')
        
        if not x_col:
            # Find categorical column
            cat_cols = df.select_dtypes(include=['object', 'category']).columns
            if len(cat_cols) > 0:
                x_col = cat_cols[0]
            else:
                x_col = df.columns[0]
        
        if not y_col:
            # Find numeric column
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            if len(numeric_cols) > 0:
                y_col = numeric_cols[0]

        if y_col:
            fig = px.bar(df, x=x_col, y=y_col, title=f'Bar Plot: {x_col} vs {y_col}')
        else:
            # Count plot
            value_counts = df[x_col].value_counts()
            fig = px.bar(x=value_counts.index, y=value_counts.values, 
                        title=f'Count Plot of {x_col}')

        filename = f"{self.output_dir}/barplot_{x_col}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        fig.write_html(filename)

        return {
            "success": True,
            "plot_path": filename,
            "plot_type": "bar",
            "summary": f"Created bar plot for {x_col}"
        }

    except Exception as e:
        return {"error": f"Bar plot creation failed: {str(e)}"}

def _heatmap(self, df: pd.DataFrame, **kwargs) -> Dict[str, Any]:
    """Create heatmap"""
    try:
        # Get numeric columns for correlation heatmap
        numeric_df = df.select_dtypes(include=[np.number])
        if numeric_df.empty:
            return {"error": "No numeric columns found for heatmap"}

        # Calculate correlation matrix
        corr_matrix = numeric_df.corr()

        fig = px.imshow(
            corr_matrix,
            text_auto=True,
            aspect="auto",
            title="Correlation Heatmap"
        )

        filename = f"{self.output_dir}/heatmap_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        fig.write_html(filename)

        return {
            "success": True,
            "plot_path": filename,
            "plot_type": "heatmap",
            "summary": "Created correlation heatmap of numeric variables"
        }

    except Exception as e:
        return {"error": f"Heatmap creation failed: {str(e)}"}

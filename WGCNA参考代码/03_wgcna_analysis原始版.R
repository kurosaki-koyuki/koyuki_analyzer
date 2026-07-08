################################################################################
# Script: 03_wgcna_analysis.R
# Description: WGCNA (Weighted Gene Co-expression Network Analysis)
################################################################################

#' Initialize WGCNA analysis
#' @param n_threads Number of threads to use (proportion of available cores)
init_wgcna <- function(n_threads = 0.75) {
  enableWGCNAThreads(nThreads = n_threads * parallel::detectCores())
  cat("WGCNA initialized with", floor(n_threads * parallel::detectCores()), "threads\n")
}

#' Check data quality for WGCNA
#' @param expr_matrix Expression matrix (genes in rows, samples in columns)
#' @return Cleaned expression matrix
check_wgcna_data <- function(expr_matrix) {
  cat("Checking data quality for WGCNA\n")
  
  # Transpose for WGCNA format
  data_mat <- t(expr_matrix)
  
  # Check for good samples and genes
  gsg <- goodSamplesGenes(data_mat, verbose = 3)
  
  if (!gsg$allOK) {
    # Remove bad genes
    if (sum(!gsg$goodGenes) > 0) {
      printFlush(paste("Removing genes:", 
                      paste(names(data_mat)[!gsg$goodGenes], collapse = ",")))
    }
    # Remove bad samples
    if (sum(!gsg$goodSamples) > 0) {
      printFlush(paste("Removing samples:", 
                      paste(rownames(data_mat)[!gsg$goodSamples], collapse = ",")))
    }
    data_mat <- data_mat[gsg$goodSamples, gsg$goodGenes]
  }
  
  cat("Data dimensions after QC:", nrow(data_mat), "samples,", ncol(data_mat), "genes\n")
  
  return(data_mat)
}

#' Plot sample dendrogram
#' @param data_mat WGCNA format data matrix (samples in rows)
#' @param trait_data Trait data frame
#' @param save_path Path to save plot
plot_sample_dendrogram <- function(data_mat, trait_data = NULL, save_path = NULL) {
  cat("Creating sample dendrogram\n")
  
  # Create sample tree
  sample_tree <- hclust(dist(data_mat), method = "average")
  
  if (!is.null(save_path)) {
    pdf(save_path, width = 12, height = 8)
  }
  
  par(mar = c(0, 4, 2, 0))
  plot(sample_tree, 
       main = "Sample Clustering", 
       sub = "", 
       xlab = "", 
       cex.lab = 1.5,
       cex.axis = 1, 
       cex.main = 1.5)
  
  # Add trait heatmap if provided
  if (!is.null(trait_data)) {
    # Convert traits to colors
    trait_colors <- numbers2colors(as.numeric(factor(trait_data$Cluster)),
                                  colors = rainbow(length(unique(trait_data$Cluster))),
                                  signed = FALSE)
    
    plotDendroAndColors(sample_tree, trait_colors,
                        groupLabels = "Cluster",
                        cex.dendroLabels = 0.8,
                        marAll = c(1, 4, 3, 1),
                        cex.rowText = 0.01,
                        main = "Sample dendrogram and trait heatmap")
  }
  
  if (!is.null(save_path)) {
    dev.off()
    cat("Sample dendrogram saved to:", save_path, "\n")
  }
}

#' Choose soft threshold power
#' @param data_mat WGCNA format data matrix
#' @param network_type Network type ("unsigned", "signed", "signed hybrid")
#' @param save_path Path to save plot
#' @return Soft threshold analysis results
choose_soft_threshold <- function(data_mat, 
                                 network_type = "unsigned",
                                 save_path = NULL) {
  
  cat("Choosing soft threshold power\n")
  
  # Test range of powers
  powers <- c(seq(1, 10, by = 1), seq(12, 20, by = 2))
  
  # Call the network topology analysis function
  sft <- pickSoftThreshold(
    data_mat,
    networkType = network_type,
    powerVector = powers,
    RsquaredCut = 0.85,
    verbose = 5
  )
  
  cat("Recommended power:", sft$powerEstimate, "\n")
  
  # Plot results
  if (!is.null(save_path)) {
    pdf(save_path, width = 12, height = 6)
  }
  
  par(mfrow = c(1, 2))
  
  # Scale independence
  plot(sft$fitIndices[, 1], 
       -sign(sft$fitIndices[, 3]) * sft$fitIndices[, 2],
       xlab = "Soft Threshold (power)",
       ylab = "Scale Free Topology Model Fit, signed R^2",
       type = "n",
       main = "Scale independence")
  text(sft$fitIndices[, 1], 
       -sign(sft$fitIndices[, 3]) * sft$fitIndices[, 2],
       labels = powers, cex = 1, col = "red")
  abline(h = 0.85, col = "red", lty = 2)
  
  # Mean connectivity
  plot(sft$fitIndices[, 1], sft$fitIndices[, 5],
       xlab = "Soft Threshold (power)",
       ylab = "Mean Connectivity",
       type = "n",
       main = "Mean connectivity")
  text(sft$fitIndices[, 1], sft$fitIndices[, 5],
       labels = powers, cex = 1, col = "red")
  
  if (!is.null(save_path)) {
    dev.off()
    cat("Soft threshold plots saved to:", save_path, "\n")
  }
  
  return(sft)
}

#' Construct network and identify modules
#' @param data_mat WGCNA format data matrix
#' @param power Soft threshold power
#' @param min_module_size Minimum module size
#' @param merge_cut_height Module merge cut height
#' @return Network construction results
construct_network <- function(data_mat,
                             power,
                             min_module_size = 30,
                             merge_cut_height = 0.25) {
  
  cat("\n========== Network Construction ==========\n")
  cat("Power:", power, "\n")
  cat("Minimum module size:", min_module_size, "\n")
  cat("Merge cut height:", merge_cut_height, "\n")
  
  net <- blockwiseModules(
    data_mat,
    power = power,
    maxBlockSize = ncol(data_mat),
    corType = "pearson",
    networkType = "unsigned",
    TOMType = "unsigned",
    minModuleSize = min_module_size,
    mergeCutHeight = merge_cut_height,
    numericLabels = TRUE,
    saveTOMs = TRUE,
    saveTOMFileBase = "TOM",
    verbose = 3
  )
  
  # Module statistics
  module_table <- table(net$colors)
  cat("\nModule sizes:\n")
  print(module_table)
  cat("==========================================\n\n")
  
  return(net)
}

#' Calculate module-trait correlations
#' @param net Network object from blockwiseModules
#' @param trait_data Trait data frame
#' @return Module-trait correlation results
calculate_module_trait_correlation <- function(net, trait_data) {
  cat("Calculating module-trait correlations\n")
  
  # Get module eigengenes
  MEs <- net$MEs
  
  # Rename columns
  colnames(MEs) <- paste0("ME", labels2colors(
    as.numeric(str_replace_all(colnames(MEs), "ME", ""))
  ))
  MEs <- orderMEs(MEs)
  
  # Process traits
  trait_numeric <- trait_data
  for (col in colnames(trait_numeric)) {
    if (is.character(trait_numeric[[col]]) || is.factor(trait_numeric[[col]])) {
      trait_numeric[[col]] <- as.numeric(factor(trait_numeric[[col]]))
    }
  }
  
  # Calculate correlations
  module_trait_cor <- cor(MEs, trait_numeric, use = "p")
  module_trait_p <- corPvalueStudent(module_trait_cor, nrow(trait_numeric))
  
  return(list(
    module_eigengenes = MEs,
    correlation = module_trait_cor,
    p_value = module_trait_p
  ))
}

#' Plot module-trait heatmap
#' @param module_trait_results Results from calculate_module_trait_correlation
#' @param save_path Path to save plot
plot_module_trait_heatmap <- function(module_trait_results, save_path = NULL) {
  
  # Create text matrix for display
  text_matrix <- paste0(
    signif(module_trait_results$correlation, 2), "\n(",
    signif(module_trait_results$p_value, 1), ")"
  )
  dim(text_matrix) <- dim(module_trait_results$correlation)
  
  if (!is.null(save_path)) {
    pdf(save_path, width = 10, height = 8)
  }
  
  par(mar = c(6, 8.5, 3, 3))
  labeledHeatmap(
    Matrix = module_trait_results$correlation,
    xLabels = colnames(module_trait_results$correlation),
    yLabels = rownames(module_trait_results$correlation),
    cex.lab = 1,
    ySymbols = rownames(module_trait_results$correlation),
    colorLabels = FALSE,
    colors = blueWhiteRed(50),
    textMatrix = text_matrix,
    setStdMargins = FALSE,
    cex.text = 0.8,
    zlim = c(-1, 1),
    main = "Module-Trait Relationships"
  )
  
  if (!is.null(save_path)) {
    dev.off()
    cat("Module-trait heatmap saved to:", save_path, "\n")
  }
}

#' Extract hub genes from specific module
#' @param data_mat WGCNA format data matrix
#' @param net Network object
#' @param module_color Module color
#' @param trait_data Trait data
#' @param mm_cutoff Module membership cutoff
#' @param gs_cutoff Gene significance cutoff
#' @return Hub gene list
extract_hub_genes <- function(data_mat, net, module_color,
                             trait_data, mm_cutoff = 0.8,
                             gs_cutoff = 0.2) {
  
  cat("Extracting hub genes from", module_color, "module\n")
  
  # Get module genes
  module_labels <- labels2colors(net$colors)
  module_genes <- names(net$colors)[module_labels == module_color]
  
  # Calculate module membership
  MEs <- net$MEs
  colnames(MEs) <- paste0("ME", labels2colors(
    as.numeric(str_replace_all(colnames(MEs), "ME", ""))
  ))
  
  gene_module_membership <- cor(data_mat, MEs, use = "p")
  
  # Calculate gene significance
  gene_trait_significance <- cor(data_mat, trait_data, use = "p")
  
  # Get MM and GS for module genes
  column <- paste0("ME", module_color)
  MM <- abs(gene_module_membership[module_genes, column])
  GS <- abs(gene_trait_significance[module_genes, 1])
  
  # Filter hub genes
  hub_genes <- module_genes[MM > mm_cutoff & GS > gs_cutoff]
  
  cat("Found", length(hub_genes), "hub genes\n")
  
  return(list(
    hub_genes = hub_genes,
    module_genes = module_genes,
    MM = MM,
    GS = GS
  ))
}

#' Run complete WGCNA pipeline
#' @param expr_matrix Expression matrix
#' @param trait_data Trait data
#' @param output_dir Output directory
#' @return WGCNA results
run_wgcna_pipeline <- function(expr_matrix, trait_data, 
                              output_dir = "results/wgcna/") {
  
  cat("\n========== Starting WGCNA Analysis ==========\n")
  
  # Initialize
  init_wgcna()
  
  # Check data
  data_mat <- check_wgcna_data(expr_matrix)
  
  # Sample clustering
  plot_sample_dendrogram(
    data_mat, 
    trait_data,
    file.path(output_dir, "sample_dendrogram.pdf")
  )
  
  # Choose soft threshold
  sft <- choose_soft_threshold(
    data_mat,
    save_path = file.path(output_dir, "soft_threshold.pdf")
  )
  
  # Construct network
  net <- construct_network(
    data_mat,
    power = sft$powerEstimate
  )
  
  # Module-trait correlation
  module_trait_results <- calculate_module_trait_correlation(net, trait_data)
  
  # Plot heatmap
  plot_module_trait_heatmap(
    module_trait_results,
    file.path(output_dir, "module_trait_heatmap.pdf")
  )
  
  cat("============================================\n\n")
  
  return(list(
    data_mat = data_mat,
    soft_threshold = sft,
    network = net,
    module_trait = module_trait_results
  ))
}

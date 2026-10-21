#!/usr/bin/env python3
# modules/synths/src/vista/builder.py

import logging
from typing import List, Dict, Any
from sentence_transformers import util
import numpy as np
import umap
# TODO: determine later if this may be utilized on our concept tags to categorize and then perform search on our fuzzy anchors with loss function for repetition [2051a566-e4df-45e1-8ffb-a5f9ab706b18]
from sklearn.mixture import GaussianMixture
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class RaptorTreeBuilder:
    """Recursively clusters and summarizes code blocks into a hierarchical knowledge tree."""
    
    def __init__(self, embedder, llm_client, graph_linker, cluster_threshold: float = 0.75):
        self.embedder = embedder
        self.llm = llm_client
        self.graph = graph_linker
        self.cluster_threshold = cluster_threshold
        self._leaves = []

    def set_leaves(self, sliding_windows: List[Dict[str, Any]]):
        """Seeds the builder with the base code chunks (leaf nodes)."""
        self._leaves = sliding_windows

    def _cluster_nodes(self, nodes: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Reduces high-dim embeddings via UMAP and applies GMM for soft clustering."""
        if len(nodes) <= 3:
            return [nodes]  # Too few nodes to effectively cluster

        embeddings = np.array([node["embedding"] for node in nodes if "embedding" in node])
        if len(embeddings) != len(nodes):
            return [[node] for node in nodes]

        # 1. Dimensionality reduction using UMAP (Cosine metric optimized for text/code embeddings)
        n_neighbors = max(2, min(15, len(nodes) - 1))
        n_components = min(10, len(nodes) - 1)
        
        reducer = umap.UMAP(
            n_neighbors=n_neighbors,
            n_components=n_components,
            metric='cosine',
            random_state=42
        )
        reduced_embeddings = reducer.fit_transform(embeddings)

        # 2. Gaussian Mixture Models for soft clustering
        # Dynamically scale component count based on dataset size, bounded between 2 and 8
        n_components_gmm = max(2, min(8, int(np.sqrt(len(nodes)))))
        
        gmm = GaussianMixture(n_components=n_components_gmm, covariance_type='full', random_state=42)
        gmm.fit(reduced_embeddings)
        
        # Extract cluster membership probabilities
        probabilities = gmm.predict_proba(reduced_embeddings)

        # 3. Group nodes using a soft probability threshold (e.g., 25% membership)
        clusters = [[] for _ in range(n_components_gmm)]
        for idx, node in enumerate(nodes):
            matched_indices = np.where(probabilities[idx] > 0.25)[0]
            for cluster_idx in matched_indices:
                clusters[cluster_idx].append(node)

        # Clean up empty clusters and fallback if everything collapsed
        valid_clusters = [c for c in clusters if c]
        return valid_clusters if valid_clusters else [nodes]


    def _summarize_cluster(self, cluster: List[Dict[str, Any]], level: int) -> Dict[str, Any]:
        """Prompts the LLM to summarize a cluster of nodes."""
        # Combine the text of all nodes in the cluster
        combined_text = "\n\n---\n\n".join([node.get("content", node.get("summary", "")) for node in cluster])
        
        prompt = (
            "You are an expert software architect. Below is a cluster of related code snippets "
            "or architectural summaries. Synthesize them into a single, comprehensive summary "
            "that explains their collective purpose and how they interact.\n\n"
            f"{combined_text}"
        )
        
        # Call the LLM (using your existing executor/llm client)
        summary_text = self.llm.generate(prompt)
        
        # Embed the new summary for the next recursive layer
        summary_embedding = self.embedder.encode(summary_text, task_type="search_document")[0]
        
        return {
            "type": "summary_node",
            "level": level,
            "summary": summary_text,
            "embedding": summary_embedding,
            "children": cluster
        }

    def build(self) -> Dict[str, Any]:
        """Executes the RAPTOR loop until a root node is formed."""
        if not self._leaves:
            logger.warning("No leaf nodes provided. Call set_leaves() first.")
            return {}

        current_layer = self._leaves
        level = 1
        
        while len(current_layer) > 1:
            logger.info(f"Building RAPTOR layer {level} with {len(current_layer)} nodes...")
            
            clusters = self._cluster_nodes(current_layer)
            
            # If the clustering algorithm couldn't group anything, force a termination 
            # to prevent an infinite loop
            if len(clusters) == len(current_layer):
                logger.warning("Clustering converged early. Forcing single root node.")
                clusters = [current_layer]
                
            next_layer = []
            for cluster in clusters:
                if len(cluster) == 1:
                    next_layer.append(cluster[0])  # Pass through unclustered nodes
                else:
                    parent_node = self._summarize_cluster(cluster, level)
                    next_layer.append(parent_node)
                    
            current_layer = next_layer
            level += 1
            
        root_node = current_layer[0]
        logger.info(f"RAPTOR tree complete. Root node generated at level {level - 1}.")
        
        # TODO: Persist the tree to Neo4j here using self.graph [97d90e07-07c9-47d3-bc54-9a75e4068499]
        
        return root_node

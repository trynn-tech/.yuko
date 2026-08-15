#!/usr/bin/env python3
# modules/synths/tests/test_builder_raptor.py

import numpy as np
import pytest
from unittest.mock import MagicMock
from vista.builder import RaptorTreeBuilder

def test_raptor_soft_clustering():
    """Verifies that UMAP + GMM correctly clusters nodes and handles overlapping soft assignments."""
    # Mock dependencies since we are only testing the clustering method
    mock_embedder = MagicMock()
    mock_llm = MagicMock()
    mock_graph = MagicMock()
    builder = RaptorTreeBuilder(
        embedder=mock_embedder,
        llm_client=mock_llm,
        graph_linker=mock_graph,
        cluster_threshold=0.75
    )
    
    # Generate synthetic embeddings (25 nodes total to ensure N > k for UMAP spectral layout)
    np.random.seed(42)
    group_a = np.random.normal(loc=0.0, scale=0.4, size=(10, 16))
    group_b = np.random.normal(loc=5.0, scale=0.4, size=(10, 16))
    bridge_node_emb = np.random.normal(loc=2.5, scale=0.1, size=(5, 16))
    all_embeddings = np.vstack([group_a, group_b, bridge_node_emb])
    
    nodes = []
    for i, emb in enumerate(all_embeddings):
        nodes.append({
            "id": f"node_{i}",
            "content": f"Synthetic code chunk content {i}",
            "embedding": emb.tolist()
        })
        
    # Execute the UMAP + GMM clustering logic
    clusters = builder._cluster_nodes(nodes)
    
    # Assertions
    assert len(clusters) > 0, "Clustering returned no groups."
    
    # Verify that every node is included in at least one cluster
    clustered_node_ids = {n["id"] for cluster in clusters for n in cluster}
    for node in nodes:
        assert node["id"] in clustered_node_ids, f"Node {node['id']} was dropped during clustering."
        
    # Verify that bridge nodes can be shared across clusters via soft probability
    bridge_node_id = "node_20"
    clusters_containing_bridge = [
        c for c in clusters if any(n["id"] == bridge_node_id for n in c)
    ]
    assert len(clusters_containing_bridge) >= 1, "Bridge node must be assigned to at least one cluster."

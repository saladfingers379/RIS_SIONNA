from __future__ import annotations

from typing import Any, Dict, Tuple

import numpy as np


def _set_seed(seed: int) -> None:
    import random
    import tensorflow as tf

    random.seed(seed)
    np.random.seed(seed)
    tf.random.set_seed(seed)


def train_autoencoder(features: np.ndarray, cfg: Dict[str, Any]) -> Dict[str, Any]:
    import tensorflow as tf

    model_cfg = cfg.get("model", {}) if isinstance(cfg, dict) else {}
    embedding_dim = int(model_cfg.get("embedding_dim", 2))
    hidden_dims = model_cfg.get("hidden_dims", [128, 64])
    epochs = int(model_cfg.get("epochs", 200))
    lr = float(model_cfg.get("learning_rate", 1e-3))
    adj_weight = float(model_cfg.get("adjacency_weight", 0.2))
    spread_weight = float(model_cfg.get("spread_weight", 0.05))
    repulsion_weight = float(model_cfg.get("repulsion_weight", 0.02))
    normalize = bool(model_cfg.get("normalize_features", True))
    seed = int(model_cfg.get("seed", 7))

    _set_seed(seed)

    x = features.astype(np.float32)
    mean = np.mean(x, axis=0, keepdims=True)
    std = np.std(x, axis=0, keepdims=True) + 1e-8
    if normalize:
        x_norm = (x - mean) / std
    else:
        x_norm = x

    input_dim = x_norm.shape[1]
    encoder_layers = [tf.keras.layers.Input(shape=(input_dim,))]
    for dim in hidden_dims:
        encoder_layers.append(tf.keras.layers.Dense(int(dim), activation="relu"))
    encoder_layers.append(tf.keras.layers.Dense(embedding_dim, activation=None))
    encoder = tf.keras.Sequential(encoder_layers, name="encoder")

    decoder_layers = [tf.keras.layers.Input(shape=(embedding_dim,))]
    for dim in reversed(hidden_dims):
        decoder_layers.append(tf.keras.layers.Dense(int(dim), activation="relu"))
    decoder_layers.append(tf.keras.layers.Dense(input_dim, activation=None))
    decoder = tf.keras.Sequential(decoder_layers, name="decoder")

    optimizer = tf.keras.optimizers.Adam(learning_rate=lr)
    x_tensor = tf.convert_to_tensor(x_norm, dtype=tf.float32)

    # Pre-compute feature distance matrix for distance-preserving loss.
    # Use a random subset of pairs to keep it efficient.
    n_samples = x_norm.shape[0]
    feat_dists = None
    if repulsion_weight > 0 and n_samples > 2:
        from scipy.spatial.distance import pdist, squareform
        feat_dists_sq = squareform(pdist(x_norm, metric="euclidean"))
        # Normalize to [0, 1]
        d_max = feat_dists_sq.max() + 1e-8
        feat_dists_norm = tf.convert_to_tensor(
            (feat_dists_sq / d_max).astype(np.float32)
        )

    history = {"loss": [], "recon": [], "adj": [], "spread": [], "repulsion": []}
    for _ in range(epochs):
        with tf.GradientTape() as tape:
            z = encoder(x_tensor)
            recon = decoder(z)
            recon_loss = tf.reduce_mean(tf.square(x_tensor - recon))

            # Adjacency loss: consecutive points should be close
            if n_samples > 1:
                adj_loss = tf.reduce_mean(tf.square(z[1:] - z[:-1]))
            else:
                adj_loss = tf.constant(0.0)

            # Spread loss: prevent embedding collapse by penalizing
            # low variance across the embedding dimensions
            z_var = tf.reduce_mean(tf.math.reduce_variance(z, axis=0))
            spread_loss = 1.0 / (z_var + 1e-6)

            # Distance-preserving repulsion: points with different CSI
            # features should be far apart in the embedding
            if repulsion_weight > 0 and feat_dists is not None:
                # Pairwise embedding distances
                z_exp_i = tf.expand_dims(z, 1)  # (N, 1, D)
                z_exp_j = tf.expand_dims(z, 0)  # (1, N, D)
                emb_dists = tf.sqrt(tf.reduce_sum(
                    tf.square(z_exp_i - z_exp_j), axis=-1
                ) + 1e-8)
                emb_dists_norm = emb_dists / (tf.reduce_max(emb_dists) + 1e-8)
                repulsion_loss = tf.reduce_mean(
                    tf.square(emb_dists_norm - feat_dists_norm)
                )
            else:
                repulsion_loss = tf.constant(0.0)

            loss = (recon_loss
                    + adj_weight * adj_loss
                    + spread_weight * spread_loss
                    + repulsion_weight * repulsion_loss)
        vars_all = encoder.trainable_variables + decoder.trainable_variables
        grads = tape.gradient(loss, vars_all)
        optimizer.apply_gradients(zip(grads, vars_all))
        history["loss"].append(float(loss.numpy()))
        history["recon"].append(float(recon_loss.numpy()))
        history["adj"].append(float(adj_loss.numpy()))
        history["spread"].append(float(spread_loss.numpy()))
        history["repulsion"].append(float(repulsion_loss.numpy()))

    z_out = encoder(x_tensor).numpy()
    recon_out = decoder(tf.convert_to_tensor(z_out, dtype=tf.float32)).numpy()
    if normalize:
        recon_out = recon_out * std + mean

    return {
        "embeddings": z_out,
        "reconstruction": recon_out,
        "history": history,
        "feature_mean": mean.reshape(-1),
        "feature_std": std.reshape(-1),
        "normalized": normalize,
    }

"""Local patches for Sionna RT multi-RIS correctness."""

from __future__ import annotations

import logging

from typing import Any


_APPLIED = False
_SVD_FALLBACK_WARNED = False
logger = logging.getLogger(__name__)


def reset_svd_cpu_fallback_flag() -> None:
    """Clear the per-process RIS SVD fallback marker."""

    global _SVD_FALLBACK_WARNED
    _SVD_FALLBACK_WARNED = False


def svd_cpu_fallback_used() -> bool:
    """Return whether the RIS curvature SVD fell back to CPU."""

    return bool(_SVD_FALLBACK_WARNED)


def _safe_curvature_svd(solver_cm, matrix):
    """Run the RIS curvature SVD with a CPU fallback for unstable GPU kernels."""
    global _SVD_FALLBACK_WARNED

    try:
        return solver_cm.tf.linalg.svd(matrix)
    except Exception as exc:
        tf_errors = getattr(solver_cm.tf, "errors", None)
        invalid_arg = getattr(tf_errors, "InvalidArgumentError", ())
        op_error = getattr(tf_errors, "OpError", ())
        if invalid_arg and not isinstance(exc, (invalid_arg, op_error)):
            raise
        if not _SVD_FALLBACK_WARNED:
            logger.warning(
                "RIS reflection SVD failed on the active TensorFlow device; retrying on CPU. Error: %s",
                exc,
            )
            _SVD_FALLBACK_WARNED = True
        with solver_cm.tf.device("/CPU:0"):
            try:
                return solver_cm.tf.linalg.svd(matrix)
            except Exception:
                eye = solver_cm.tf.eye(
                    solver_cm.tf.shape(matrix)[-1],
                    batch_shape=solver_cm.tf.shape(matrix)[:1],
                    dtype=matrix.dtype,
                )
                regularized = matrix + solver_cm.tf.cast(1.0e-9, matrix.dtype) * eye
                return solver_cm.tf.linalg.svd(regularized)


def apply_sionna_multi_ris_patch() -> None:
    """Patch Sionna RT multi-RIS handling to avoid cross-RIS mixing.

    This stays within official APIs but corrects a logic bug in the
    coverage-map RIS reflection path where per-RIS rays were padded and
    concatenated without aligning associated ray metadata.
    """
    global _APPLIED
    if _APPLIED:
        return

    try:
        from sionna.rt import solver_cm  # type: ignore
    except Exception:
        return

    # Guard: only patch if the attribute exists and has the expected method.
    if not hasattr(solver_cm, "SolverCoverageMap"):
        return

    orig_cls = solver_cm.SolverCoverageMap
    if getattr(orig_cls, "_multi_ris_patch_applied", False):
        _APPLIED = True
        return

    def _apply_ris_reflection_fixed(
        self,
        active_ind,
        int_point,
        previous_int_point,
        primitives,
        e_field,
        field_es,
        field_ep,
        samples_tx_indices,
        k_tx,
        radii_curv,
        dirs_curv,
        angular_opening,
    ):
        # Re-implement with per-RIS filtering and aligned outputs.
        act_data = self._extract_active_ris_rays(
            active_ind,
            int_point,
            previous_int_point,
            primitives,
            e_field,
            field_es,
            field_ep,
            samples_tx_indices,
            k_tx,
            radii_curv,
            dirs_curv,
            angular_opening,
        )
        act_e_field = act_data[0]
        act_field_es = act_data[1]
        act_field_ep = act_data[2]
        act_int_point = act_data[3]
        act_k_i = act_data[4]
        act_length = act_data[5]
        act_samples_tx_indices = act_data[6]
        act_k_tx = act_data[7]
        act_radii_curv = act_data[8]
        act_dirs_curv = act_data[9]
        act_ris_ind = act_data[10]
        act_ang_opening = act_data[11]

        # Outputs (concatenated in matching order)
        rdtype = self._rdtype
        dtype = self._dtype
        out_e_field = solver_cm.tf.zeros([0, act_e_field.shape[1], 2], dtype)
        out_field_es = solver_cm.tf.zeros([0, 3], rdtype)
        out_field_ep = solver_cm.tf.zeros([0, 3], rdtype)
        out_int_point = solver_cm.tf.zeros([0, 3], rdtype)
        out_k_r = solver_cm.tf.zeros([0, 3], rdtype)
        out_normals = solver_cm.tf.zeros([0, 3], rdtype)
        out_samples_tx_indices = solver_cm.tf.zeros([0], solver_cm.tf.int32)
        out_k_tx = solver_cm.tf.zeros([0, 3], rdtype)
        out_radii_curv = solver_cm.tf.zeros([0, 2], rdtype)
        out_dirs_curv = solver_cm.tf.zeros([0, 2, 3], rdtype)
        out_ang_opening = solver_cm.tf.zeros([0], rdtype)

        for ris_idx, ris in enumerate(self._scene.ris.values()):
            # Indices of rays hitting this RIS
            this_ris_sample_ind = solver_cm.tf.where(
                solver_cm.tf.equal(act_ris_ind, ris_idx)
            )[:, 0]
            if solver_cm.tf.size(this_ris_sample_ind) == 0:
                continue

            # Gather incident ray directions for this RIS
            k_i = solver_cm.tf.gather(act_k_i, this_ris_sample_ind, axis=0)

            # Boolean indicating the RIS side (front only)
            normal = ris.world_normal
            normal = solver_cm.tf.expand_dims(normal, axis=0)
            hit_front = -solver_cm.tf.math.sign(solver_cm.dot(k_i, normal))
            hit_front = solver_cm.tf.greater(hit_front, 0.0)
            this_ris_sample_ind = solver_cm.tf.gather(
                this_ris_sample_ind, solver_cm.tf.where(hit_front)[:, 0]
            )
            if solver_cm.tf.size(this_ris_sample_ind) == 0:
                continue

            # Extract data relevant to this RIS
            int_point = solver_cm.tf.gather(act_int_point, this_ris_sample_ind, axis=0)
            k_i = solver_cm.tf.gather(act_k_i, this_ris_sample_ind, axis=0)
            e_field = solver_cm.tf.gather(act_e_field, this_ris_sample_ind, axis=0)
            field_es = solver_cm.tf.gather(act_field_es, this_ris_sample_ind, axis=0)
            field_ep = solver_cm.tf.gather(act_field_ep, this_ris_sample_ind, axis=0)
            radii_curv = solver_cm.tf.gather(act_radii_curv, this_ris_sample_ind, axis=0)
            dirs_curv = solver_cm.tf.gather(act_dirs_curv, this_ris_sample_ind, axis=0)
            length = solver_cm.tf.gather(act_length, this_ris_sample_ind, axis=0)

            # Compute and apply the spreading factor
            sf = solver_cm.compute_spreading_factor(radii_curv[:, 0], radii_curv[:, 1], length)
            sf = solver_cm.expand_to_rank(sf, solver_cm.tf.rank(e_field), -1)
            sf = solver_cm.tf.complex(sf, solver_cm.tf.zeros_like(sf))
            e_field *= sf
            radii_curv = radii_curv + solver_cm.tf.expand_dims(length, axis=1)

            # Incidence phase gradient - Eq.(9)
            grad_i = k_i - normal * solver_cm.dot(normal, k_i)[:, solver_cm.tf.newaxis]
            grad_i *= -self._scene.wavenumber

            # Transform interaction points to LCS of this RIS
            rot_mat = solver_cm.rotation_matrix(ris.orientation)[solver_cm.tf.newaxis]
            int_point_lcs = int_point - ris.position[solver_cm.tf.newaxis]
            int_point_lcs = solver_cm.tf.linalg.matvec(rot_mat, int_point_lcs, transpose_a=True)
            int_point_lcs = int_point_lcs[:, 1:]

            # Spatial modulation coefficient
            gamma_m, grad_m, hessian_m = ris(int_point_lcs, return_grads=True)
            mode_powers = ris.amplitude_profile.mode_powers
            mode = solver_cm.tf.random.categorical(
                logits=[solver_cm.tf.math.log(mode_powers)],
                num_samples=solver_cm.tf.shape(int_point_lcs)[0],
                dtype=solver_cm.tf.int32,
            )[0]
            gamma_m = solver_cm.tf.gather(solver_cm.tf.transpose(gamma_m, perm=[1, 0]), mode, batch_dims=1)
            grad_m = solver_cm.tf.gather(solver_cm.tf.transpose(grad_m, perm=[1, 0, 2]), mode, batch_dims=1)
            hessian_m = solver_cm.tf.gather(
                solver_cm.tf.transpose(hessian_m, perm=[1, 0, 2, 3]), mode, batch_dims=1
            )
            grad_m = solver_cm.tf.linalg.matvec(rot_mat, grad_m)
            hessian_m = solver_cm.tf.matmul(rot_mat, solver_cm.tf.matmul(hessian_m, rot_mat, transpose_b=True))

            # Total phase gradient
            grad = grad_i + grad_m

            # Reflected direction
            k_r = -grad / self._scene.wavenumber
            k_r += solver_cm.tf.sqrt(
                1 - solver_cm.tf.reduce_sum(k_r**2, axis=-1, keepdims=True)
            ) * normal

            # Linear transformation operator - Eq.(22)
            l = -solver_cm.outer(k_r, normal)
            l /= solver_cm.tf.reduce_sum(k_r * normal, axis=-1, keepdims=True)[..., solver_cm.tf.newaxis]
            l += solver_cm.tf.eye(3, batch_shape=solver_cm.tf.shape(l)[:1], dtype=l.dtype)

            # Curvature matrices
            q_i = (1 / solver_cm.expand_to_rank(radii_curv[:, 0], 3, -1)) * solver_cm.outer(
                dirs_curv[:, 0], dirs_curv[:, 0]
            )
            q_i += (1 / solver_cm.expand_to_rank(radii_curv[:, 1], 3, -1)) * solver_cm.outer(
                dirs_curv[:, 1], dirs_curv[:, 1]
            )
            q_r = solver_cm.tf.matmul(q_i - 1 / self._scene.wavenumber * hessian_m, l)
            q_r = solver_cm.tf.matmul(l, q_r, transpose_a=True)
            e, v, _ = _safe_curvature_svd(solver_cm, q_r)
            radii_curv = 1 / e[:, :2]
            dirs_curv = solver_cm.tf.transpose(v[..., :2], perm=[0, 2, 1])

            # Basis vectors for incoming field
            theta_i, phi_i = solver_cm.theta_phi_from_unit_vec(k_i)
            e_i_s = solver_cm.theta_hat(theta_i, phi_i)
            e_i_p = solver_cm.phi_hat(phi_i)

            # Component transform
            mat_comp = solver_cm.component_transform(field_es, field_ep, e_i_s, e_i_p)
            mat_comp = solver_cm.tf.complex(mat_comp, solver_cm.tf.zeros_like(mat_comp))
            mat_comp = mat_comp[:, solver_cm.tf.newaxis]

            # Outgoing field
            e_field = solver_cm.tf.linalg.matvec(mat_comp, e_field)
            e_field *= solver_cm.expand_to_rank(gamma_m, 3, -1)

            # Basis vectors for reflected field
            theta_r, phi_r = solver_cm.theta_phi_from_unit_vec(k_r)
            field_es = solver_cm.theta_hat(theta_r, phi_r)
            field_ep = solver_cm.phi_hat(phi_r)

            # Gather aligned metadata
            samples_tx_indices = solver_cm.tf.gather(act_samples_tx_indices, this_ris_sample_ind, axis=0)
            k_tx = solver_cm.tf.gather(act_k_tx, this_ris_sample_ind, axis=0)
            ang_opening = solver_cm.tf.gather(act_ang_opening, this_ris_sample_ind, axis=0)

            # Append
            out_e_field = solver_cm.tf.concat([out_e_field, e_field], axis=0)
            out_field_es = solver_cm.tf.concat([out_field_es, field_es], axis=0)
            out_field_ep = solver_cm.tf.concat([out_field_ep, field_ep], axis=0)
            out_int_point = solver_cm.tf.concat([out_int_point, int_point], axis=0)
            out_k_r = solver_cm.tf.concat([out_k_r, k_r], axis=0)
            normal_tile = solver_cm.tf.tile(normal, [solver_cm.tf.shape(k_r)[0], 1])
            out_normals = solver_cm.tf.concat([out_normals, normal_tile], axis=0)
            out_samples_tx_indices = solver_cm.tf.concat([out_samples_tx_indices, samples_tx_indices], axis=0)
            out_k_tx = solver_cm.tf.concat([out_k_tx, k_tx], axis=0)
            out_radii_curv = solver_cm.tf.concat([out_radii_curv, radii_curv], axis=0)
            out_dirs_curv = solver_cm.tf.concat([out_dirs_curv, dirs_curv], axis=0)
            out_ang_opening = solver_cm.tf.concat([out_ang_opening, ang_opening], axis=0)

        return (
            out_e_field,
            out_field_es,
            out_field_ep,
            out_int_point,
            out_k_r,
            out_normals,
            out_samples_tx_indices,
            out_k_tx,
            out_radii_curv,
            out_dirs_curv,
            out_ang_opening,
        )

    # Monkeypatch
    orig_cls._apply_ris_reflection = _apply_ris_reflection_fixed  # type: ignore[attr-defined]
    orig_cls._multi_ris_patch_applied = True  # type: ignore[attr-defined]
    _APPLIED = True

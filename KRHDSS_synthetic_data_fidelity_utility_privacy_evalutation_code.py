#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KRHDSS Synthetic Data Evaluation Pipeline

Manuscript:"Synthetic Data Generation of Health and Demographic Surveillance Systems Data: A Case Study in a Low- and Middle-Income Country"
Authors: Dorcas G. Mwigereri, Nigel T. Kamotho, et al.

This single-file pipeline reproduces the core analyses reported in the manuscript:
  1) Fidelity: Univariate (marginals) and Bivariate (joint) analyses
  2) Associations: Uncertainty coefficient (Theil's U) matrix
  3) Machine-Learning Utility: Random Forest classifier predicting 'latuse_r'
     - Train on: REAL R6, CTGAN R6, CopulaGAN R6
     - Evaluate on: REAL R8
  4) Privacy: Attribute inference risk using the Anonymeter framework
     - Scenario A (Plausible Attacker): aux = ['sex','age_cohort'], secret = 'hivstatus'
     - Scenario B (Highly Informed): aux = all columns except the secret

Quick start
-----------
python krhdss_synth_eval_pipeline.py \
  --real-r6 path/to/real_r6.csv \
  --real-r8 path/to/real_r8.csv \
  --syn-ctgan-r6 path/to/syn_CTGAN_r6.csv \
  --syn-ctgan-r8 path/to/syn_CTGAN_r8.csv \
  --syn-copula-r6 path/to/syn_CopulaGAN_r6.csv \
  --syn-copula-r8 path/to/syn_CopulaGAN_r8.csv \
  --outdir results/

Dependencies (install beforehand)
---------------------------------
pip install pandas numpy matplotlib seaborn scikit-learn dython anonymeter

Tested with:
- Python >= 3.9
- pandas >= 1.5
- scikit-learn >= 1.2
- dython >= 0.7.5
- anonymeter >= 0.4.1

"""

from __future__ import annotations

import argparse
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
import seaborn as sns

from sklearn.compose import ColumnTransformer
from sklearn.metrics import (accuracy_score, auc, classification_report,
                             f1_score, precision_recall_curve, precision_score,
                             recall_score, roc_auc_score, roc_curve)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.ensemble import RandomForestClassifier

# Associations (Theil's U)
from dython.nominal import associations

# Privacy (Anonymeter)
from anonymeter.evaluators import InferenceEvaluator

from scipy.stats import ks_2samp, ranksums


# ----------------------------
# Configuration & Utilities
# ----------------------------

RANDOM_STATE = 42
np.random.seed(RANDOM_STATE)


@dataclass
class Inputs:
    real_r6: Path
    real_r8: Path
    syn_ctgan_r6: Path
    syn_ctgan_r8: Path
    syn_copula_r6: Path
    syn_copula_r8: Path
    outdir: Path
    id_like_cols: Tuple[str, ...] = (
        'individ_id', 'permid', 'hhno', 'village_id', 'doi', 'dob'
    )
    target: str = 'latuse_r'  # ML target
    # For privacy 'plausible' scenario
    plausible_aux: Tuple[str, ...] = ('sex', 'age_cohort')
    plausible_secret: str = 'hivstatus'


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def setup_logging(outdir: Path) -> None:
    ensure_dir(outdir)
    log_path = outdir / 'run.log'
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s: %(message)s',
        handlers=[
            logging.FileHandler(log_path, mode='w', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )


def load_csv(path: Path) -> pd.DataFrame:
    logging.info(f'Loading: {path}')
    df = pd.read_csv(
        path,
        keep_default_na=False,  # preserve 'NA' strings where present
        skipinitialspace=True,
        low_memory=False
    )
    return df


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize minor naming differences."""
    df = df.copy()
    # Align immunization field name variants used across scripts
    if 'full_immune' in df.columns and 'full_immun' not in df.columns:
        df.rename(columns={'full_immune': 'full_immun'}, inplace=True)
    if 'full_immun' in df.columns and 'full_immune' not in df.columns:
        # keep 'full_immun' as canonical
        pass
    # Ensure all columns are strings for categorical analyses
    for col in df.columns:
        df[col] = df[col].astype(str)
    return df


def save_json(obj, path: Path) -> None:
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


# ----------------------------
# Fidelity: Univariate & Bivariate
# ----------------------------

def univariate_percentage_counts(dfs: Dict[str, pd.DataFrame],
                                 variables: List[str],
                                 outdir: Path) -> pd.DataFrame:
    """
    For each categorical variable, compute normalized value counts per dataset.
    Returns a tidy long-form DataFrame and writes a wide summary CSV.
    """
    logging.info('Running univariate percentage counts...')
    rows = []
    for ds_name, df in dfs.items():
        for var in variables:
            if var not in df.columns:
                continue
            vc = df[var].value_counts(normalize=True, dropna=False) * 100.0
            for val, pct in vc.items():
                rows.append({
                    'dataset': ds_name,
                    'variable': var,
                    'value': str(val),
                    'percent': round(float(pct), 6)
                })
    tidy = pd.DataFrame(rows)
    tidy.to_csv(outdir / 'univariate_percentage_counts_long.csv', index=False)

    # Pivot to wide for convenience
    wide = tidy.pivot_table(index=['variable', 'value'],
                            columns='dataset', values='percent',
                            fill_value=0.0).reset_index()
    wide.to_csv(outdir / 'univariate_percentage_counts_wide.csv', index=False)
    return tidy


def plot_univariate_bars(tidy_counts: pd.DataFrame,
                         datasets_order: List[str],
                         outdir: Path,
                         max_vars: int = 30) -> None:
    """
    Create bar plots for up to max_vars categorical variables comparing datasets.
    """
    logging.info('Plotting univariate bar charts...')
    sns.set(style='whitegrid')
    variables = tidy_counts['variable'].unique().tolist()[:max_vars]
    for var in variables:
        sub = tidy_counts[tidy_counts['variable'] == var].copy()
        plt.figure(figsize=(9, 5), dpi=200)
        ax = sns.barplot(data=sub, x='value', y='percent',
                         hue='dataset', hue_order=datasets_order)
        ax.set_title(f'Univariate Distribution: {var}')
        ax.set_xlabel(var)
        ax.set_ylabel('Percent')
        ax.tick_params(axis='x', rotation=45)
        plt.tight_layout()
        plt.savefig(outdir / f'univariate_{var}.png', bbox_inches='tight')
        plt.close()


def bivariate_crosstab_heatmap(df: pd.DataFrame,
                               var_x: str,
                               var_y: str,
                               title: str,
                               outpath: Path) -> None:
    """
    Heatmap of normalized joint distribution P(var_x, var_y).
    """
    if var_x not in df.columns or var_y not in df.columns:
        logging.warning(f'Skipping heatmap {title}: missing columns.')
        return
    tab = pd.crosstab(df[var_x], df[var_y], normalize='all') * 100.0
    plt.figure(figsize=(7, 6), dpi=200)
    sns.heatmap(tab, annot=False, cmap='viridis')
    plt.title(title)
    plt.xlabel(var_y)
    plt.ylabel(var_x)
    plt.tight_layout()
    plt.savefig(outpath, bbox_inches='tight')
    plt.close()


# ----------------------------
# Associations (Uncertainty Coefficient)
# ----------------------------

def compute_uncertainty_coefficient_matrix(df: pd.DataFrame,
                                           variables: List[str],
                                           out_csv: Path,
                                           out_png: Optional[Path] = None) -> pd.DataFrame:
    """
    Compute Theil's U association matrix using dython.associations.
    """
    logging.info(f'Computing associations for {out_csv.name}...')
    use_cols = [v for v in variables if v in df.columns]
    # dython.associations returns a dict with 'corr' (DataFrame) among others
    result = associations(df[use_cols], nominal_columns='all',
                          nom_nom_assoc='theil', compute_only=True)
    corr = result['corr']
    corr.to_csv(out_csv, index=True)
    if out_png is not None:
        plt.figure(figsize=(12, 10), dpi=200)
        sns.heatmap(corr, cmap='mako', vmin=0, vmax=1)
        plt.title(out_csv.stem)
        plt.tight_layout()
        plt.savefig(out_png, bbox_inches='tight')
        plt.close()
    return corr


# ----------------------------
# ML Utility: Random Forest
# ----------------------------

def bootstrap_ci_binary_metric(y_true: np.ndarray,
                               y_score_or_pred: np.ndarray,
                               metric: str = 'roc_auc',
                               n_boot: int = 2000,
                               seed: int = RANDOM_STATE) -> Tuple[float, float, float]:
    """
    Compute metric and bootstrap CI (percentile). Supported metrics:
      'roc_auc', 'accuracy', 'precision', 'recall', 'f1'.
    For 'roc_auc', y_score_or_pred must be positive-class probabilities.
    """
    rng = np.random.default_rng(seed)
    n = len(y_true)

    def compute(y_idx):
        yt = y_true[y_idx]
        yp = y_score_or_pred[y_idx]
        if metric == 'roc_auc':
            return roc_auc_score(yt, yp)
        elif metric == 'accuracy':
            return accuracy_score(yt, (yp >= 0.5).astype(int))
        elif metric == 'precision':
            return precision_score(yt, (yp >= 0.5).astype(int), zero_division=0)
        elif metric == 'recall':
            return recall_score(yt, (yp >= 0.5).astype(int), zero_division=0)
        elif metric == 'f1':
            return f1_score(yt, (yp >= 0.5).astype(int), zero_division=0)
        else:
            raise ValueError(f'Unknown metric: {metric}')

    base = compute(np.arange(n))
    stats = [compute(rng.integers(0, n, size=n)) for _ in range(n_boot)]
    low = float(np.percentile(stats, 2.5))
    high = float(np.percentile(stats, 97.5))
    return float(base), low, high


def fit_eval_rf(train_df: pd.DataFrame,
                test_df: pd.DataFrame,
                target: str,
                out_prefix: str,
                outdir: Path) -> Dict[str, Tuple[float, float, float]]:
    """
    Train a RandomForest on *train_df* and evaluate on *test_df* (binary target).
    Uses a OneHotEncoder over all non-target columns.
    Returns dict of metric -> (point, 95% low, 95% high).
    """
    logging.info(f'RF: training on {out_prefix} ...')

    assert target in train_df.columns and target in test_df.columns, \
        f"Target '{target}' must exist in both train and test."

    # Select categorical features and ensure strings
    X_train = train_df.drop(columns=[target]).astype(str)
    y_train_raw = train_df[target].astype(str)

    X_test = test_df.drop(columns=[target]).astype(str)
    y_test_raw = test_df[target].astype(str)

    # Convert target to binary 1/0 (Yes/No style), mapping flexible {'Y','Yes','1'} vs {'N','No','0'}
    def to_binary(series: pd.Series) -> np.ndarray:
        yes = {'Y', 'Yes', '1', 'TRUE', 'True', 'true'}
        return series.map(lambda v: 1 if str(v) in yes else 0).astype(int).values

    y_train = to_binary(y_train_raw)
    y_test = to_binary(y_test_raw)

    all_features = X_train.columns.tolist()

    pipeline = Pipeline(steps=[
        ('prep', ColumnTransformer(
            transformers=[('cat', OneHotEncoder(handle_unknown='ignore'), all_features)],
            remainder='drop'
        )),
        ('clf', RandomForestClassifier(
            n_estimators=300,
            max_depth=None,
            min_samples_split=2,
            min_samples_leaf=1,
            n_jobs=-1,
            random_state=RANDOM_STATE
        ))
    ])

    pipeline.fit(X_train, y_train)

    # Probabilities for ROC/AUC and thresholded metrics
    y_prob = pipeline.predict_proba(X_test)[:, 1]

    metrics_ci = {}
    for name in ['accuracy', 'precision', 'recall', 'f1', 'roc_auc']:
        pt, low, high = bootstrap_ci_binary_metric(y_test, y_prob, metric=name)
        metrics_ci[name] = (pt, low, high)

    # Save metrics and ROC curve
    df_metrics = pd.DataFrame([{
        'dataset_train': out_prefix,
        'dataset_test': 'REAL_R8',
        'accuracy': metrics_ci['accuracy'][0],
        'accuracy_low': metrics_ci['accuracy'][1],
        'accuracy_high': metrics_ci['accuracy'][2],
        'precision': metrics_ci['precision'][0],
        'precision_low': metrics_ci['precision'][1],
        'precision_high': metrics_ci['precision'][2],
        'recall': metrics_ci['recall'][0],
        'recall_low': metrics_ci['recall'][1],
        'recall_high': metrics_ci['recall'][2],
        'f1': metrics_ci['f1'][0],
        'f1_low': metrics_ci['f1'][1],
        'f1_high': metrics_ci['f1'][2],
        'auc_roc': metrics_ci['roc_auc'][0],
        'auc_roc_low': metrics_ci['roc_auc'][1],
        'auc_roc_high': metrics_ci['roc_auc'][2]
    }])
    df_metrics.to_csv(outdir / f'ml_metrics_{out_prefix}_vs_REAL_R8.csv', index=False)

    fpr, tpr, _ = roc_curve((y_test), y_prob)
    plt.figure(figsize=(6, 5), dpi=200)
    plt.plot(fpr, tpr, label=f'ROC AUC={metrics_ci["roc_auc"][0]:.3f} [{metrics_ci["roc_auc"][1]:.3f},{metrics_ci["roc_auc"][2]:.3f}]')
    plt.plot([0, 1], [0, 1], linestyle='--', alpha=0.6)
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title(f'ROC Curve: Train={out_prefix}, Test=REAL_R8')
    plt.legend(loc='lower right')
    plt.tight_layout()
    plt.savefig(outdir / f'roc_{out_prefix}_vs_REAL_R8.png', bbox_inches='tight')
    plt.close()

    return metrics_ci


# ----------------------------
# Privacy: Anonymeter
# ----------------------------

def run_anonymeter_inference(ori_df: pd.DataFrame,
                             syn_df: pd.DataFrame,
                             control_df: pd.DataFrame,
                             aux_cols: List[str],
                             secret: str,
                             n_attacks: Optional[int] = None,
                             n_jobs: int = -1) -> Dict[str, float]:
    """
    Run attribute inference attack and return risk and CI.
    """
    logging.info(f'Anonymeter: aux={aux_cols} secret={secret} n_attacks={n_attacks}')
    # Ensure everything is string/categorical to avoid dtype conflicts
    for df in (ori_df, syn_df, control_df):
        for col in df.columns:
            df[col] = df[col].astype(str)

    evaluator = InferenceEvaluator(
        ori=ori_df,
        syn=syn_df,
        control=control_df,
        aux_cols=aux_cols,
        secret=secret,
        n_attacks=len(syn_df) if n_attacks is None else int(n_attacks)
    )
    evaluator.evaluate(n_jobs=n_jobs)
    r = evaluator.risk()
    return {'risk': float(r.value), 'ci_low': float(r.ci[0]), 'ci_high': float(r.ci[1])}


# ----------------------------
# Main Orchestration
# ----------------------------

def main(args: Optional[List[str]] = None):
    parser = argparse.ArgumentParser(description='KRHDSS Synthetic Data Evaluation Pipeline')
    parser.add_argument('--real-r6', required=True, type=Path, help='CSV for REAL round 6 (R6)')
    parser.add_argument('--real-r8', required=True, type=Path, help='CSV for REAL round 8 (R8)')
    parser.add_argument('--syn-ctgan-r6', required=True, type=Path, help='CSV for CTGAN round 6 (R6)')
    parser.add_argument('--syn-ctgan-r8', required=True, type=Path, help='CSV for CTGAN round 8 (R8)')
    parser.add_argument('--syn-copula-r6', required=True, type=Path, help='CSV for CopulaGAN round 6 (R6)')
    parser.add_argument('--syn-copula-r8', required=True, type=Path, help='CSV for CopulaGAN round 8 (R8)')
    parser.add_argument('--outdir', required=True, type=Path, help='Output directory')
    parser.add_argument('--bivar-x', default='age_cohort', help='Bivariate X variable (default: age_cohort)')
    parser.add_argument('--bivar-y', default='relation', help='Bivariate Y variable (default: relation)')
    parser.add_argument('--vars-json', type=Path, default=None,
                        help='Optional JSON file with keys: {"fidelity_vars":[...], "assoc_vars":[...]}')
    parser.add_argument('--privacy-n-attacks', type=int, default=None,
                        help='Override number of attacks for privacy evaluation (default: len(syn))')
    opts = parser.parse_args(args)

    ensure_dir(opts.outdir)
    setup_logging(opts.outdir)

    # Load and standardize
    real_r6 = standardize_columns(load_csv(opts.real_r6))
    real_r8 = standardize_columns(load_csv(opts.real_r8))

    ctgan_r6 = standardize_columns(load_csv(opts.syn_ctgan_r6))
    ctgan_r8 = standardize_columns(load_csv(opts.syn_ctgan_r8))

    copula_r6 = standardize_columns(load_csv(opts.syn_copula_r6))
    copula_r8 = standardize_columns(load_csv(opts.syn_copula_r8))

    # Optionally drop known ID-like columns if present
    def drop_id_like(df: pd.DataFrame, cols: Tuple[str, ...]) -> pd.DataFrame:
        return df.drop(columns=[c for c in cols if c in df.columns], errors='ignore')

    id_like_cols = ('individ_id', 'permid', 'hhno', 'village_id', 'doi', 'dob', 'event_date', 'others')
    real_r6 = drop_id_like(real_r6, id_like_cols)
    real_r8 = drop_id_like(real_r8, id_like_cols)
    ctgan_r6 = drop_id_like(ctgan_r6, id_like_cols)
    ctgan_r8 = drop_id_like(ctgan_r8, id_like_cols)
    copula_r6 = drop_id_like(copula_r6, id_like_cols)
    copula_r8 = drop_id_like(copula_r8, id_like_cols)

    # Variables (if provided, enforce; otherwise infer categorical set excluding target)
    if opts.vars_json and opts.vars_json.exists():
        with open(opts.vars_json, 'r', encoding='utf-8') as f:
            var_cfg = json.load(f)
        fidelity_vars = var_cfg.get('fidelity_vars', [])
        assoc_vars = var_cfg.get('assoc_vars', fidelity_vars)
    else:
        # Use intersection of columns that likely appear in all datasets.
        common_cols = set(real_r6.columns) & set(real_r8.columns) & set(ctgan_r6.columns) & set(ctgan_r8.columns) & set(copula_r6.columns) & set(copula_r8.columns)
        # Reserve target
        common_cols = [c for c in sorted(common_cols) if c != 'latuse_r']
        fidelity_vars = common_cols
        assoc_vars = common_cols

    save_json({'fidelity_vars': fidelity_vars, 'assoc_vars': assoc_vars}, opts.outdir / 'variables_used.json')

    # ---------------- Fidelity: Univariate ----------------
    dfs_r6 = {
        'REAL_R6': real_r6,
        'CTGAN_R6': ctgan_r6,
        'COPULA_R6': copula_r6
    }
    dfs_r8 = {
        'REAL_R8': real_r8,
        'CTGAN_R8': ctgan_r8,
        'COPULA_R8': copula_r8
    }
    uni_r6 = univariate_percentage_counts(dfs_r6, fidelity_vars, opts.outdir / Path('univariate_R6'))
    uni_r8 = univariate_percentage_counts(dfs_r8, fidelity_vars, opts.outdir / Path('univariate_R8'))
    # Plot (up to 30 variables per round by default)
    plot_univariate_bars(uni_r6, ['REAL_R6', 'CTGAN_R6', 'COPULA_R6'], opts.outdir / Path('univariate_R6_plots'))
    plot_univariate_bars(uni_r8, ['REAL_R8', 'CTGAN_R8', 'COPULA_R8'], opts.outdir / Path('univariate_R8_plots'))

    # ---------------- Fidelity: Bivariate ----------------
    ensure_dir(opts.outdir / 'bivariate_heatmaps')
    bivariate_crosstab_heatmap(real_r6, opts.bivar_x, opts.bivar_y,
                               title=f'REAL_R6: {opts.bivar_x} vs {opts.bivar_y}',
                               outpath=opts.outdir / 'bivariate_heatmaps' / 'REAL_R6_heatmap.png')
    bivariate_crosstab_heatmap(ctgan_r6, opts.bivar_x, opts.bivar_y,
                               title=f'CTGAN_R6: {opts.bivar_x} vs {opts.bivar_y}',
                               outpath=opts.outdir / 'bivariate_heatmaps' / 'CTGAN_R6_heatmap.png')
    bivariate_crosstab_heatmap(copula_r6, opts.bivar_x, opts.bivar_y,
                               title=f'COPULA_R6: {opts.bivar_x} vs {opts.bivar_y}',
                               outpath=opts.outdir / 'bivariate_heatmaps' / 'COPULA_R6_heatmap.png')

    bivariate_crosstab_heatmap(real_r8, opts.bivar_x, opts.bivar_y,
                               title=f'REAL_R8: {opts.bivar_x} vs {opts.bivar_y}',
                               outpath=opts.outdir / 'bivariate_heatmaps' / 'REAL_R8_heatmap.png')
    bivariate_crosstab_heatmap(ctgan_r8, opts.bivar_x, opts.bivar_y,
                               title=f'CTGAN_R8: {opts.bivar_x} vs {opts.bivar_y}',
                               outpath=opts.outdir / 'bivariate_heatmaps' / 'CTGAN_R8_heatmap.png')
    bivariate_crosstab_heatmap(copula_r8, opts.bivar_x, opts.bivar_y,
                               title=f'COPULA_R8: {opts.bivar_x} vs {opts.bivar_y}',
                               outpath=opts.outdir / 'bivariate_heatmaps' / 'COPULA_R8_heatmap.png')

    # ---------------- Associations (Theil's U) ----------------
    ass_dir = opts.outdir / 'associations'
    ensure_dir(ass_dir)
    compute_uncertainty_coefficient_matrix(real_r6, assoc_vars, ass_dir / 'associations_REAL_R6.csv', ass_dir / 'associations_REAL_R6.png')
    compute_uncertainty_coefficient_matrix(ctgan_r6, assoc_vars, ass_dir / 'associations_CTGAN_R6.csv', ass_dir / 'associations_CTGAN_R6.png')
    compute_uncertainty_coefficient_matrix(copula_r6, assoc_vars, ass_dir / 'associations_COPULA_R6.csv', ass_dir / 'associations_COPULA_R6.png')

    # --- K-S and Wilcoxon Tests --- 
    logging.info("Performing K-S and Wilcoxon tests on association distributions (R6)...")
    try:
        association_matrices = {
            'Real': pd.read_csv(ass_dir / 'associations_REAL_R6.csv', index_col=0),
            'CTGAN': pd.read_csv(ass_dir / 'associations_CTGAN_R6.csv', index_col=0),
            'CopulaGAN': pd.read_csv(ass_dir / 'associations_COPULA_R6.csv', index_col=0),
        }

        real_assoc_flat = association_matrices['Real'].values.flatten()
        ctgan_assoc_flat = association_matrices['CTGAN'].values.flatten()
        copula_assoc_flat = association_matrices['CopulaGAN'].values.flatten()

        # Remove self-correlations (diagonal of 1) for a more meaningful comparison
        real_assoc_flat = real_assoc_flat[real_assoc_flat < 1]
        ctgan_assoc_flat = ctgan_assoc_flat[ctgan_assoc_flat < 1]
        copula_assoc_flat = copula_assoc_flat[copula_assoc_flat < 1]

        # Kolmogorov-Smirnov Test
        ks_ctgan = ks_2samp(real_assoc_flat, ctgan_assoc_flat)
        ks_copula = ks_2samp(real_assoc_flat, copula_assoc_flat)

        # Wilcoxon Rank-Sum Test (Mann-Whitney U equivalent for independent samples)
        wilcox_ctgan = ranksums(real_assoc_flat, ctgan_assoc_flat)
        wilcox_copula = ranksums(real_assoc_flat, copula_assoc_flat)

        results_table = pd.DataFrame({
            'Dataset': ['CTGAN', 'CopulaGAN'],
            'K-S D-statistic': [ks_ctgan.statistic, ks_copula.statistic],
            'K-S p-value': [ks_ctgan.pvalue, ks_copula.pvalue],
            'Wilcoxon statistic': [wilcox_ctgan.statistic, wilcox_copula.statistic],
            'Wilcoxon p-value': [wilcox_ctgan.pvalue, wilcox_copula.pvalue],
            'Median Association': [np.median(ctgan_assoc_flat), np.median(copula_assoc_flat)]
        })

        logging.info("\n--- Statistical Test Results (R6; corresponds to Table 1) ---")
        logging.info("Median of Real Data Associations: %.4f", float(np.median(real_assoc_flat)))
        logging.info("\n%s", results_table.round(4).to_string(index=False))

        results_table.to_csv(ass_dir / 'fidelity_statistical_tests_R6.csv', index=False)
    except Exception as e:
        logging.warning("K-S/Wilcoxon tests (R6) skipped due to error: %s", e)


    compute_uncertainty_coefficient_matrix(real_r8, assoc_vars, ass_dir / 'associations_REAL_R8.csv', ass_dir / 'associations_REAL_R8.png')
    compute_uncertainty_coefficient_matrix(ctgan_r8, assoc_vars, ass_dir / 'associations_CTGAN_R8.csv', ass_dir / 'associations_CTGAN_R8.png')
    compute_uncertainty_coefficient_matrix(copula_r8, assoc_vars, ass_dir / 'associations_COPULA_R8.csv', ass_dir / 'associations_COPULA_R8.png')

    # ---------------- ML Utility (RF, train on R6; test on REAL R8) ----------------
    ml_dir = opts.outdir / 'ml_utility_rf'
    ensure_dir(ml_dir)

    # For ML, select common columns + target; ensure target present in all sets used
    required_cols = set(['latuse_r'])
    for df in [real_r6, real_r8, ctgan_r6, copula_r6]:
        required_cols |= set(df.columns)
    # For safety: only keep columns present in both train and test for each run
    common_train_test = list(set(real_r8.columns) & set(real_r6.columns))
    if 'latuse_r' not in real_r6.columns or 'latuse_r' not in real_r8.columns:
        raise ValueError("Target column 'latuse_r' must exist in both REAL R6 and REAL R8 CSVs.")

    # Train on REAL R6
    metrics_real = fit_eval_rf(
        train_df=real_r6[common_train_test + ['latuse_r']].dropna(subset=['latuse_r']),
        test_df=real_r8[common_train_test + ['latuse_r']].dropna(subset=['latuse_r']),
        target='latuse_r',
        out_prefix='REAL_R6',
        outdir=ml_dir
    )
    # Train on CTGAN R6
    common_ctgan = list(set(real_r8.columns) & set(ctgan_r6.columns))
    if 'latuse_r' in ctgan_r6.columns:
        metrics_ctgan = fit_eval_rf(
            train_df=ctgan_r6[common_ctgan + ['latuse_r']].dropna(subset=['latuse_r']),
            test_df=real_r8[common_ctgan + ['latuse_r']].dropna(subset=['latuse_r']),
            target='latuse_r',
            out_prefix='CTGAN_R6',
            outdir=ml_dir
        )
    else:
        logging.warning("CTGAN_R6 missing 'latuse_r'; skipping RF for CTGAN.")
    # Train on CopulaGAN R6
    common_copula = list(set(real_r8.columns) & set(copula_r6.columns))
    if 'latuse_r' in copula_r6.columns:
        metrics_copula = fit_eval_rf(
            train_df=copula_r6[common_copula + ['latuse_r']].dropna(subset=['latuse_r']),
            test_df=real_r8[common_copula + ['latuse_r']].dropna(subset=['latuse_r']),
            target='latuse_r',
            out_prefix='COPULA_R6',
            outdir=ml_dir
        )
    else:
        logging.warning("COPULA_R6 missing 'latuse_r'; skipping RF for CopulaGAN.")

    # ---------------- Privacy (Anonymeter) ----------------
    priv_dir = opts.outdir / 'privacy_anonymeter'
    ensure_dir(priv_dir)

    # Scenario A: plausible attacker (aux=['sex','age_cohort'], secret='hivstatus')
    plausible_results = []
    for label, syn_df, ori_df, ctrl_df in [
        ('CTGAN_R6', ctgan_r6, real_r6, real_r8),
        ('CTGAN_R8', ctgan_r8, real_r8, real_r6),
        ('COPULA_R6', copula_r6, real_r6, real_r8),
        ('COPULA_R8', copula_r8, real_r8, real_r6)
    ]:
        if all(col in syn_df.columns for col in ['sex', 'age_cohort', 'hivstatus']):
            r = run_anonymeter_inference(
                ori_df=ori_df.copy(), syn_df=syn_df.copy(), control_df=ctrl_df.copy(),
                aux_cols=['sex', 'age_cohort'], secret='hivstatus',
                n_attacks=opts.privacy_n_attacks
            )
            r['dataset'] = label
            r['scenario'] = 'plausible'
            plausible_results.append(r)
        else:
            logging.warning(f'{label}: missing columns for plausible scenario; skipping.')
    pd.DataFrame(plausible_results).to_csv(priv_dir / 'privacy_plausible.csv', index=False)

    # Scenario B: highly informed attacker (aux = all columns minus secret)
    informed_results = []
    for label, syn_df, ori_df, ctrl_df in [
        ('CTGAN_R6', ctgan_r6, real_r6, real_r8),
        ('CTGAN_R8', ctgan_r8, real_r8, real_r6),
        ('COPULA_R6', copula_r6, real_r6, real_r8),
        ('COPULA_R8', copula_r8, real_r8, real_r6)
    ]:
        # use the same secret as above for comparability if present
        secret = 'hivstatus'
        if secret in syn_df.columns:
            aux_cols = [c for c in syn_df.columns if c != secret]
            r = run_anonymeter_inference(
                ori_df=ori_df.copy(), syn_df=syn_df.copy(), control_df=ctrl_df.copy(),
                aux_cols=aux_cols, secret=secret,
                n_attacks=opts.privacy_n_attacks
            )
            r['dataset'] = label
            r['scenario'] = 'informed_all_except_secret'
            informed_results.append(r)
        else:
            logging.warning(f'{label}: missing "{secret}" for informed scenario; skipping.')
    pd.DataFrame(informed_results).to_csv(priv_dir / 'privacy_informed.csv', index=False)

    logging.info('Done. All outputs written to: %s', str(opts.outdir.resolve()))


if __name__ == '__main__':
    main()

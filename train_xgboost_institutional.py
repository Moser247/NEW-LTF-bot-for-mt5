"""
XGBOOST TRAINING FOR INSTITUTIONAL ORDER FLOW

Trains XGBoost classifier to predict profitable trade setups
Shows which institutional patterns have the most predictive power
"""

import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.metrics import (
    classification_report, confusion_matrix,
    roc_auc_score, precision_recall_curve, auc
)
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import pickle
import os
from datetime import datetime


class XGBoostTrainer:
    """
    Train XGBoost model on institutional order flow features
    """

    def __init__(
        self,
        n_estimators: int = 300,
        max_depth: int = 7,
        learning_rate: float = 0.05,
        min_child_weight: int = 3,
        subsample: float = 0.8,
        colsample_bytree: float = 0.8,
        gamma: float = 0.1,
        n_splits: int = 5
    ):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.min_child_weight = min_child_weight
        self.subsample = subsample
        self.colsample_bytree = colsample_bytree
        self.gamma = gamma
        self.n_splits = n_splits
        self.model = None
        self.feature_names = None

    def load_training_data(self, csv_path: str) -> tuple:
        """Load and prepare training data"""
        print(f"Loading training data from {csv_path}...")

        df = pd.read_csv(csv_path)
        print(f"Loaded {len(df)} samples")

        # Print class distribution
        print(f"\nClass distribution:")
        print(f"Profitable (1): {df['is_profitable'].sum()} ({df['is_profitable'].mean()*100:.2f}%)")
        print(f"Not profitable (0): {(1-df['is_profitable']).sum()} ({(1-df['is_profitable'].mean())*100:.2f}%)")

        print(f"\nDirection breakdown:")
        print(df['trade_direction'].value_counts())

        # Define feature columns (exclude target and metadata)
        exclude_cols = [
            'timestamp', 'price', 'is_profitable', 'max_profit_reached',
            'bars_to_target', 'trade_direction', 'vwap'  # vwap is just reference
        ]

        feature_cols = [col for col in df.columns if col not in exclude_cols]

        print(f"\n{len(feature_cols)} features for training")

        # Prepare features and target
        X = df[feature_cols].copy()
        y = df['is_profitable'].copy()

        # Handle NaN and inf values
        X = X.replace([np.inf, -np.inf], np.nan)
        X = X.fillna(0)

        self.feature_names = feature_cols

        return X, y, df

    def train_model(self, X, y) -> dict:
        """Train XGBoost model with cross-validation"""
        print("\n" + "=" * 80)
        print("TRAINING XGBOOST MODEL")
        print("=" * 80)

        # Calculate class weights for imbalanced data
        n_samples = len(y)
        n_pos = y.sum()
        n_neg = n_samples - n_pos
        scale_pos_weight = n_neg / n_pos if n_pos > 0 else 1

        print(f"\nClass imbalance ratio: {scale_pos_weight:.2f}")
        print(f"Using scale_pos_weight: {scale_pos_weight:.2f}")

        # Initialize XGBoost classifier
        self.model = xgb.XGBClassifier(
            n_estimators=self.n_estimators,
            max_depth=self.max_depth,
            learning_rate=self.learning_rate,
            min_child_weight=self.min_child_weight,
            subsample=self.subsample,
            colsample_bytree=self.colsample_bytree,
            gamma=self.gamma,
            scale_pos_weight=scale_pos_weight,
            random_state=42,
            n_jobs=-1,
            eval_metric='logloss'
        )

        # Time series cross-validation
        print(f"\nPerforming {self.n_splits}-fold Time Series Cross-Validation...")
        tscv = TimeSeriesSplit(n_splits=self.n_splits)

        cv_scores = []
        fold_results = []

        for fold, (train_idx, val_idx) in enumerate(tscv.split(X), 1):
            print(f"\nFold {fold}/{self.n_splits}")
            print(f"Train: {len(train_idx)} samples, Val: {len(val_idx)} samples")

            X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

            # Train on this fold
            self.model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                verbose=False
            )

            # Predict on validation set
            y_pred = self.model.predict(X_val)
            y_pred_proba = self.model.predict_proba(X_val)[:, 1]

            # Calculate metrics
            from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

            accuracy = accuracy_score(y_val, y_pred)
            precision = precision_score(y_val, y_pred, zero_division=0)
            recall = recall_score(y_val, y_pred, zero_division=0)
            f1 = f1_score(y_val, y_pred, zero_division=0)

            try:
                roc_auc = roc_auc_score(y_val, y_pred_proba)
            except:
                roc_auc = 0.0

            print(f"Accuracy: {accuracy:.4f}")
            print(f"Precision: {precision:.4f}")
            print(f"Recall: {recall:.4f}")
            print(f"F1 Score: {f1:.4f}")
            print(f"ROC AUC: {roc_auc:.4f}")

            cv_scores.append({
                'fold': fold,
                'accuracy': accuracy,
                'precision': precision,
                'recall': recall,
                'f1': f1,
                'roc_auc': roc_auc
            })

        # Train final model on all data
        print("\n" + "=" * 80)
        print("Training final model on all data...")
        self.model.fit(X, y, verbose=False)

        # Calculate average CV scores
        avg_scores = {
            'accuracy': np.mean([s['accuracy'] for s in cv_scores]),
            'precision': np.mean([s['precision'] for s in cv_scores]),
            'recall': np.mean([s['recall'] for s in cv_scores]),
            'f1': np.mean([s['f1'] for s in cv_scores]),
            'roc_auc': np.mean([s['roc_auc'] for s in cv_scores])
        }

        print("\n" + "=" * 80)
        print("AVERAGE CROSS-VALIDATION SCORES")
        print("=" * 80)
        for metric, score in avg_scores.items():
            print(f"{metric.upper()}: {score:.4f}")

        return {
            'cv_scores': cv_scores,
            'avg_scores': avg_scores
        }

    def analyze_feature_importance(self) -> pd.DataFrame:
        """Analyze and visualize feature importance"""
        print("\n" + "=" * 80)
        print("FEATURE IMPORTANCE ANALYSIS")
        print("=" * 80)

        # Get feature importance
        importance = self.model.feature_importances_
        feature_importance_df = pd.DataFrame({
            'feature': self.feature_names,
            'importance': importance
        }).sort_values('importance', ascending=False)

        print("\nTop 20 Most Important Features:")
        print("=" * 80)
        for i, row in feature_importance_df.head(20).iterrows():
            print(f"{row['feature']:40s} {row['importance']:.6f}")

        # Save detailed importance
        importance_path = '/home/user/NEW-LTF-bot-for-mt5/feature_importance.csv'
        feature_importance_df.to_csv(importance_path, index=False)
        print(f"\n✓ Feature importance saved to: {importance_path}")

        # Create visualization
        self.plot_feature_importance(feature_importance_df.head(20))

        return feature_importance_df

    def plot_feature_importance(self, importance_df: pd.DataFrame):
        """Plot feature importance"""
        plt.figure(figsize=(12, 10))
        plt.barh(importance_df['feature'], importance_df['importance'])
        plt.xlabel('Importance')
        plt.title('Top 20 Feature Importance - XGBoost')
        plt.gca().invert_yaxis()
        plt.tight_layout()

        plot_path = '/home/user/NEW-LTF-bot-for-mt5/feature_importance.png'
        plt.savefig(plot_path, dpi=150, bbox_inches='tight')
        print(f"✓ Feature importance plot saved to: {plot_path}")
        plt.close()

    def evaluate_on_full_dataset(self, X, y, df):
        """Evaluate model on full dataset and analyze by threshold"""
        print("\n" + "=" * 80)
        print("FULL DATASET EVALUATION")
        print("=" * 80)

        # Predict probabilities
        y_pred_proba = self.model.predict_proba(X)[:, 1]

        # Add predictions to dataframe
        df['ml_probability'] = y_pred_proba

        print("\nProbability distribution:")
        print(f"Mean: {y_pred_proba.mean():.4f}")
        print(f"Std: {y_pred_proba.std():.4f}")
        print(f"Min: {y_pred_proba.min():.4f}")
        print(f"Max: {y_pred_proba.max():.4f}")

        # Analyze by probability threshold
        print("\n" + "=" * 80)
        print("PERFORMANCE BY PROBABILITY THRESHOLD")
        print("=" * 80)

        thresholds = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80]
        threshold_analysis = []

        for thresh in thresholds:
            selected = df[df['ml_probability'] >= thresh]

            if len(selected) > 0:
                win_rate = selected['is_profitable'].mean()
                n_trades = len(selected)
                n_wins = selected['is_profitable'].sum()
                avg_max_profit = selected['max_profit_reached'].mean()

                threshold_analysis.append({
                    'threshold': thresh,
                    'n_trades': n_trades,
                    'n_wins': n_wins,
                    'win_rate': win_rate,
                    'avg_max_profit': avg_max_profit
                })

                print(f"Threshold >= {thresh:.2f}: "
                      f"{n_trades:4d} trades, "
                      f"{n_wins:4d} wins, "
                      f"Win Rate: {win_rate*100:5.2f}%, "
                      f"Avg Max Profit: {avg_max_profit*100:.3f}%")

        # Save threshold analysis
        threshold_df = pd.DataFrame(threshold_analysis)
        threshold_path = '/home/user/NEW-LTF-bot-for-mt5/threshold_analysis.csv'
        threshold_df.to_csv(threshold_path, index=False)
        print(f"\n✓ Threshold analysis saved to: {threshold_path}")

        return df, threshold_df

    def save_model(self, path: str = None):
        """Save trained model"""
        if path is None:
            os.makedirs('/home/user/NEW-LTF-bot-for-mt5/models', exist_ok=True)
            path = '/home/user/NEW-LTF-bot-for-mt5/models/xgboost_institutional.pkl'

        with open(path, 'wb') as f:
            pickle.dump({
                'model': self.model,
                'feature_names': self.feature_names
            }, f)

        print(f"\n✓ Model saved to: {path}")

        # Also save as JSON for portability
        json_path = path.replace('.pkl', '.json')
        self.model.save_model(json_path)
        print(f"✓ Model also saved as JSON: {json_path}")


def main():
    """Main execution"""
    print("=" * 80)
    print("XGBOOST INSTITUTIONAL ORDER FLOW TRAINING")
    print("=" * 80)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Initialize trainer
    trainer = XGBoostTrainer(
        n_estimators=300,
        max_depth=7,
        learning_rate=0.05,
        min_child_weight=3,
        subsample=0.8,
        colsample_bytree=0.8,
        gamma=0.1,
        n_splits=5
    )

    # Load data
    data_path = '/home/user/NEW-LTF-bot-for-mt5/ml_training_data.csv'
    X, y, df = trainer.load_training_data(data_path)

    # Train model
    training_results = trainer.train_model(X, y)

    # Analyze feature importance
    feature_importance = trainer.analyze_feature_importance()

    # Evaluate on full dataset
    df_with_predictions, threshold_analysis = trainer.evaluate_on_full_dataset(X, y, df)

    # Save predictions
    predictions_path = '/home/user/NEW-LTF-bot-for-mt5/ml_predictions.csv'
    df_with_predictions.to_csv(predictions_path, index=False)
    print(f"\n✓ Predictions saved to: {predictions_path}")

    # Save model
    trainer.save_model()

    print("\n" + "=" * 80)
    print("TRAINING COMPLETE!")
    print("=" * 80)
    print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total samples: {len(df)}")
    print(f"Positive samples: {y.sum()} ({y.mean()*100:.2f}%)")
    print(f"Features used: {len(trainer.feature_names)}")
    print(f"\nCross-validation performance:")
    for metric, score in training_results['avg_scores'].items():
        print(f"  {metric}: {score:.4f}")

    print(f"\nTop 5 most important features:")
    for i, row in feature_importance.head(5).iterrows():
        print(f"  {row['feature']}: {row['importance']:.6f}")

    # Find optimal threshold
    optimal = threshold_analysis.sort_values('win_rate', ascending=False).iloc[0]
    print(f"\nBest threshold: {optimal['threshold']:.2f}")
    print(f"  Trades: {optimal['n_trades']}")
    print(f"  Win rate: {optimal['win_rate']*100:.2f}%")


if __name__ == "__main__":
    main()

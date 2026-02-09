"""
Device Visibility Analyzer

Analyzes device-level visibility changes using 7-day vs 7-day comparisons.
NO API calls - operates purely on stored database metrics.

Classification:
- Significant Drop: impressions ↓ ≥40%
- Significant Gain: impressions ↑ ≥40%
- Flat: everything else
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Any
from db_persistence import DatabasePersistence


class DeviceVisibilityAnalyzer:
    """Analyzes device-level visibility changes"""
    
    def __init__(self, db: DatabasePersistence):
        self.db = db
        self.threshold_pct = 40.0  # 40% threshold for drop/gain
    
    def fetch_last_14_days(self, property_id: str) -> List[Dict[str, Any]]:
        """
        Fetch last 14 days of device metrics for a property
        
        Returns:
            List of device metrics (max 42 rows: 14 days * 3 devices)
        """
        return self.db.fetch_device_metrics_last_14_days(property_id)
    
    def split_by_device(self, metrics: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Group metrics by device type
        
        Returns:
            Dict with keys: 'desktop', 'mobile', 'tablet'
        """
        device_groups = {
            'desktop': [],
            'mobile': [],
            'tablet': []
        }
        
        for metric in metrics:
            device = metric.get('device', '').lower()
            if device in device_groups:
                device_groups[device].append(metric)
        
        return device_groups
    
    def split_windows(self, device_metrics: List[Dict[str, Any]]) -> tuple:
        """
        Split device metrics into last 7 days vs previous 7 days
        
        Returns:
            (last_7_rows, previous_7_rows)
        """
        # Metrics are already sorted by date DESC
        # Last 7 days = rows 0-6
        # Previous 7 days = rows 7-13
        
        if len(device_metrics) < 14:
            # Insufficient data for this device
            return ([], [])
        
        last_7 = device_metrics[0:7]
        previous_7 = device_metrics[7:14]
        
        return (last_7, previous_7)
    
    def aggregate_window(self, window: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Aggregate metrics for a 7-day window
        
        Returns:
            Dict with clicks, impressions, ctr, avg_position
        """
        if not window:
            return {
                'clicks': 0,
                'impressions': 0,
                'ctr': 0.0,
                'avg_position': 0.0
            }
        
        # SUM for clicks and impressions
        total_clicks = sum(row['clicks'] for row in window)
        total_impressions = sum(row['impressions'] for row in window)
        
        # Recompute CTR from sums
        computed_ctr = total_clicks / total_impressions if total_impressions > 0 else 0.0
        
        # AVG for position
        avg_position = sum(float(row['position']) for row in window) / len(window) if window else 0.0
        
        return {
            'clicks': total_clicks,
            'impressions': total_impressions,
            'ctr': computed_ctr,
            'avg_position': avg_position
        }
    
    def classify_change(self, last_7_impressions: int, prev_7_impressions: int) -> str:
        """
        Classify visibility change based on impression delta
        
        Returns:
            'significant_drop', 'significant_gain', or 'flat'
        """
        if prev_7_impressions == 0:
            # Can't compute percentage change
            if last_7_impressions > 0:
                return 'significant_gain'
            return 'flat'
        
        delta_pct = ((last_7_impressions - prev_7_impressions) / prev_7_impressions) * 100
        
        if delta_pct <= -self.threshold_pct:
            return 'significant_drop'
        elif delta_pct >= self.threshold_pct:
            return 'significant_gain'
        else:
            return 'flat'
    
    def analyze_property(self, property_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze device visibility for a single property
        
        Returns:
            Dict with summary and details for each device
        """
        property_id = property_data['id']
        site_url = property_data['site_url']
        base_domain = property_data['base_domain']
        
        print(f"\n[PROPERTY] {base_domain}")
        print(f"  Site URL: {site_url}")
        
        # Fetch last 14 days
        metrics = self.fetch_last_14_days(property_id)
        
        if len(metrics) < 14:
            print(f"  [WARNING] Insufficient data: only {len(metrics)} rows available (need 42 for 3 devices)")
            return {
                'property_id': property_id,
                'site_url': site_url,
                'base_domain': base_domain,
                'insufficient_data': True,
                'rows_available': len(metrics)
            }
        
        # Group by device
        device_groups = self.split_by_device(metrics)
        
        summary = {}
        details = {}
        
        # Analyze each device
        for device in ['mobile', 'desktop', 'tablet']:
            device_metrics = device_groups[device]
            
            if len(device_metrics) < 14:
                print(f"  [DEVICE] {device}")
                print(f"    ⚠ Insufficient data ({len(device_metrics)} days)")
                summary[device] = 'insufficient_data'
                details[device] = {
                    'insufficient_data': True,
                    'days_available': len(device_metrics)
                }
                continue
            
            # Split windows
            last_7, prev_7 = self.split_windows(device_metrics)
            
            # Aggregate
            last_7_agg = self.aggregate_window(last_7)
            prev_7_agg = self.aggregate_window(prev_7)
            
            # Compute deltas
            delta_impressions = last_7_agg['impressions'] - prev_7_agg['impressions']
            delta_pct = (delta_impressions / prev_7_agg['impressions'] * 100) if prev_7_agg['impressions'] > 0 else 0.0
            
            # Classify
            classification = self.classify_change(last_7_agg['impressions'], prev_7_agg['impressions'])
            
            # Store results
            summary[device] = classification
            details[device] = {
                'last_7_impressions': last_7_agg['impressions'],
                'prev_7_impressions': prev_7_agg['impressions'],
                'delta_impressions': delta_impressions,
                'delta_pct': round(delta_pct, 1),
                'last_7_clicks': last_7_agg['clicks'],
                'prev_7_clicks': prev_7_agg['clicks'],
                'classification': classification
            }
            
            # Log
            print(f"  [DEVICE] {device}")
            print(f"    Last 7: {last_7_agg['impressions']:,} impressions")
            print(f"    Prev 7: {prev_7_agg['impressions']:,} impressions")
            
            if classification == 'significant_drop':
                print(f"    Delta: {delta_impressions:,} ({delta_pct:+.1f}%) 🔴 SIGNIFICANT DROP")
            elif classification == 'significant_gain':
                print(f"    Delta: {delta_impressions:,} ({delta_pct:+.1f}%) 🟢 SIGNIFICANT GAIN")
            else:
                print(f"    Delta: {delta_impressions:,} ({delta_pct:+.1f}%) 🟰 FLAT")
        
        return {
            'property_id': property_id,
            'site_url': site_url,
            'base_domain': base_domain,
            'insufficient_data': False,
            'summary': summary,
            'details': details
        }
    
    def analyze_all_properties(self, properties: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze device visibility for all properties
        
        Returns:
            Complete analysis results with summary and details
        """
        print("\n" + "="*80)
        print("DEVICE VISIBILITY ANALYSIS")
        print("="*80)
        print(f"Properties to analyze: {len(properties)}")
        print(f"Threshold: ±{self.threshold_pct}% impressions")
        print("="*80)
        
        results = []
        total_drops = 0
        total_gains = 0
        
        for prop in properties:
            result = self.analyze_property(prop)
            results.append(result)
            
            # Count drops and gains
            if not result.get('insufficient_data', False):
                summary = result.get('summary', {})
                for device, classification in summary.items():
                    if classification == 'significant_drop':
                        total_drops += 1
                    elif classification == 'significant_gain':
                        total_gains += 1
        
        # Print summary
        print("\n" + "="*80)
        print("DEVICE VISIBILITY SUMMARY")
        print("="*80)
        print(f"✓ Properties analyzed: {len(properties)}")
        print(f"🔴 Total significant drops: {total_drops}")
        print(f"🟢 Total significant gains: {total_gains}")
        print("="*80 + "\n")
        
        # Save to JSON
        output_dir = os.path.join(os.path.dirname(__file__), '..', 'outputs')
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, 'device_visibility_analysis.json')
        
        output_data = {
            'generated_at': datetime.now().isoformat(),
            'total_properties': len(properties),
            'total_significant_drops': total_drops,
            'total_significant_gains': total_gains,
            'threshold_pct': self.threshold_pct,
            'comparisons': results
        }
        
        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        print(f"[OUTPUT] JSON saved to: {output_file}\n")
        
        return output_data

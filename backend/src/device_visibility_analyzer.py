from __future__ import annotations
"""
Device Visibility Analyzer

Surgically refactored to compute full analytical 7v7 metrics
using canonical window logic.
NO classification, NO thresholds, NO API calls.
"""

import os
import json
from datetime import datetime
from src.config.date_windows import ANALYSIS_WINDOW_DAYS, HALF_ANALYSIS_WINDOW
from src.utils.metrics import safe_delta_pct
from src.utils.windows import get_most_recent_date, split_rows_by_window, aggregate_metrics
from src.db_persistence import DatabasePersistence


class DeviceVisibilityAnalyzer:
    """Analyzes device-level visibility changes using 7v7 metrics"""
    
    def __init__(self, db: DatabasePersistence):
        self.db = db
    
    def fetch_analysis_metrics(self, account_id: str, property_id: str) -> List[Dict[str, Any]]:
        """Fetch raw daily device metrics from database"""
        return self.db.fetch_device_metrics_for_analysis(account_id, property_id)
    
    def split_by_device(self, metrics: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group raw metrics by device type"""
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

    

    def analyze_property(self, account_id: str, property_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze device visibility for a single property using canonical windows.
        """
        property_id = property_data['id']
        site_url = property_data['site_url']
        base_domain = property_data['base_domain']
        
        print(f"\n[PROPERTY] {base_domain}")
        
        # Fetch required metrics
        metrics = self.fetch_analysis_metrics(account_id, property_id)
        
        if not metrics:
            return {
                'property_id': property_id,
                'site_url': site_url,
                'base_domain': base_domain,
                'insufficient_data': True
            }
        
        # Group by device
        device_groups = self.split_by_device(metrics)
        details = {}
        
        # Analyze each device
        for device in ['mobile', 'desktop', 'tablet']:
            device_metrics = device_groups[device]
            
            if not device_metrics:
                continue
            
            # 🟢 Use Centralized Window Logic
            most_recent_date = get_most_recent_date(device_metrics)
            last_7, prev_7 = split_rows_by_window(device_metrics, most_recent_date)
            
            # 🟢 Use Centralized Aggregation
            last_7_agg = aggregate_metrics(last_7)
            prev_7_agg = aggregate_metrics(prev_7)
            
            # 4. Compute Deltas
            impressions_delta_pct = safe_delta_pct(last_7_agg['impressions'], prev_7_agg['impressions'])
            clicks_delta_pct = safe_delta_pct(last_7_agg['clicks'], prev_7_agg['clicks'])
            ctr_delta_pct = safe_delta_pct(last_7_agg['ctr'], prev_7_agg['ctr'])
            
            # 5. Build Result Structure
            details[device] = {
                'last_7_impressions': last_7_agg['impressions'],
                'prev_7_impressions': prev_7_agg['impressions'],
                'impressions_delta_pct': round(impressions_delta_pct, 2),
                
                'last_7_clicks': last_7_agg['clicks'],
                'prev_7_clicks': prev_7_agg['clicks'],
                'clicks_delta_pct': round(clicks_delta_pct, 2),
                
                'last_7_ctr': round(last_7_agg['ctr'], 4),
                'prev_7_ctr': round(prev_7_agg['ctr'], 4),
                'ctr_delta_pct': round(ctr_delta_pct, 2)
            }
            
            # Log metrics
            print(f"  [DEVICE] {device}")
            print(f"    Impressions: {last_7_agg['impressions']:,} ({impressions_delta_pct:+.1f}%)")
            print(f"    Clicks:      {last_7_agg['clicks']:,} ({clicks_delta_pct:+.1f}%)")
            print(f"    CTR:         {last_7_agg['ctr']*100:.2f}% ({ctr_delta_pct:+.1f}%)")
        
        return {
            'property_id': property_id,
            'site_url': site_url,
            'base_domain': base_domain,
            'insufficient_data': len(details) == 0,
            'details': details
        }
    
    def analyze_all_properties(self, properties: List[Dict[str, Any]], account_id: str) -> Dict[str, Any]:
        """
        Analyze device visibility for all properties and persist results.
        """
        print("\n" + "="*80)
        print("DEVICE PERFORMANCE ANALYSIS (CANONICAL 7v7)")
        print("="*80)
        
        results = []
        for prop in properties:
            result = self.analyze_property(account_id, prop)
            results.append(result)
        
        # Save to JSON for debugging
        output_dir = os.path.join(os.path.dirname(__file__), '..', 'outputs')
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, 'device_visibility_analysis.json')
        
        output_data = {
            'generated_at': datetime.now().isoformat(),
            'total_properties': len(properties),
            'comparisons': results
        }
        
        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2)
            
        print(f"\n[DEBUG] JSON saved to: {output_file}")
        return output_data

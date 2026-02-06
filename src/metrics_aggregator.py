"""
Metrics Aggregator - Phase 4
Computes 7-day vs 7-day comparisons from stored metrics
"""

import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from decimal import Decimal


class MetricsAggregator:
    """Handles metrics aggregation and 7v7 comparison logic"""
    
    def __init__(self, db_persistence):
        """
        Initialize metrics aggregator
        
        Args:
            db_persistence: DatabasePersistence instance
        """
        self.db = db_persistence
    
    def fetch_last_14_days(self, property_id: str) -> List[Dict[str, Any]]:
        """
        Fetch the most recent 14 complete days of metrics for a property
        
        CRITICAL: Always ORDER BY date DESC LIMIT 14
        Never rely on insertion order
        
        Args:
            property_id: UUID of the property
        
        Returns:
            List of metric rows (most recent first), or empty list if <14 days
        """
        try:
            self.db.cursor.execute("""
                SELECT
                    property_id,
                    date,
                    clicks,
                    impressions,
                    ctr,
                    position
                FROM property_daily_metrics
                WHERE property_id = %s
                ORDER BY date DESC
                LIMIT 14
            """, (property_id,))
            
            rows = self.db.cursor.fetchall()
            return [dict(row) for row in rows]
        
        except Exception as e:
            print(f"[ERROR] Failed to fetch metrics for property {property_id}: {e}")
            return []
    
    def split_windows(self, rows: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Split 14 rows into two 7-day windows
        
        Args:
            rows: List of 14 metric rows (already sorted DESC by date)
        
        Returns:
            Tuple of (last_7_days, previous_7_days)
            - last_7_days: rows [0:7] (most recent)
            - previous_7_days: rows [7:14] (older)
        """
        last_7 = rows[0:7]
        previous_7 = rows[7:14]
        
        return last_7, previous_7
    
    def aggregate_window(self, window: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Aggregate metrics for a 7-day window
        
        Aggregation Rules:
        - Clicks: SUM(clicks)
        - Impressions: SUM(impressions)
        - CTR: SUM(clicks) / SUM(impressions)  ⚠️ NOT AVG(ctr)
        - Position: AVG(position)
        
        Args:
            window: List of 7 metric rows
        
        Returns:
            Dictionary with aggregated metrics
        """
        # Convert Decimal to float for JSON serialization
        total_clicks = float(sum(row['clicks'] for row in window))
        total_impressions = float(sum(row['impressions'] for row in window))
        
        # Compute CTR from sums (NOT average of CTR values)
        computed_ctr = total_clicks / total_impressions if total_impressions > 0 else 0.0
        
        # Average position (convert Decimal to float)
        avg_position = float(sum(row['position'] for row in window)) / len(window) if window else 0.0
        
        # Get date range
        dates = [row['date'] for row in window]
        start_date = min(dates)
        end_date = max(dates)
        
        return {
            'clicks': int(total_clicks),  # Convert to int for cleaner JSON
            'impressions': int(total_impressions),  # Convert to int for cleaner JSON
            'ctr': computed_ctr,
            'avg_position': avg_position,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'dates': sorted([d.strftime('%Y-%m-%d') for d in dates], reverse=True)
        }
    
    def compute_deltas(
        self, 
        last_7: Dict[str, float], 
        previous_7: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Compute deltas between two windows
        
        Args:
            last_7: Aggregated metrics for last 7 days
            previous_7: Aggregated metrics for previous 7 days
        
        Returns:
            Dictionary with deltas and percentage changes
        """
        clicks_delta = last_7['clicks'] - previous_7['clicks']
        clicks_pct = (clicks_delta / previous_7['clicks'] * 100) if previous_7['clicks'] > 0 else 0.0
        
        impressions_delta = last_7['impressions'] - previous_7['impressions']
        impressions_pct = (impressions_delta / previous_7['impressions'] * 100) if previous_7['impressions'] > 0 else 0.0
        
        ctr_delta = last_7['ctr'] - previous_7['ctr']
        ctr_pct = (ctr_delta / previous_7['ctr'] * 100) if previous_7['ctr'] > 0 else 0.0
        
        position_delta = last_7['avg_position'] - previous_7['avg_position']
        # Negative position delta = improvement (moving up in rankings)
        
        return {
            'clicks': {
                'delta': clicks_delta,
                'percentage': clicks_pct
            },
            'impressions': {
                'delta': impressions_delta,
                'percentage': impressions_pct
            },
            'ctr': {
                'delta': ctr_delta,
                'percentage': ctr_pct
            },
            'position': {
                'delta': position_delta,
                'improved': position_delta < 0  # Lower position = better
            }
        }
    
    def compute_property_comparison(self, property_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute 7v7 comparison for a single property
        
        Args:
            property_data: Dictionary with property info (id, site_url, base_domain)
        
        Returns:
            Dictionary with comparison results or insufficient_data flag
        """
        property_id = property_data['id']
        site_url = property_data['site_url']
        base_domain = property_data.get('base_domain', site_url)
        
        print(f"\n[PROPERTY] {base_domain}")
        print(f"  Site URL: {site_url}")
        
        # Fetch last 14 days
        rows = self.fetch_last_14_days(property_id)
        
        if len(rows) < 14:
            print(f"  [WARNING] Insufficient data: only {len(rows)} days available (need 14)")
            print(f"  Skipping comparison for this property\n")
            return {
                'property_id': property_id,
                'site_url': site_url,
                'base_domain': base_domain,
                'insufficient_data': True,
                'days_available': len(rows)
            }
        
        # Log data retrieval
        date_range_start = rows[-1]['date'].strftime('%Y-%m-%d')  # Oldest
        date_range_end = rows[0]['date'].strftime('%Y-%m-%d')      # Newest
        print(f"  [DATA] Retrieved 14 days of metrics ({date_range_start} → {date_range_end})")
        
        # Split into windows
        last_7, previous_7 = self.split_windows(rows)
        
        # Aggregate each window
        last_7_agg = self.aggregate_window(last_7)
        previous_7_agg = self.aggregate_window(previous_7)
        
        # Log window details
        print(f"\n  [WINDOW] Last 7 days ({last_7_agg['start_date']} → {last_7_agg['end_date']}):")
        print(f"    Dates: {', '.join(last_7_agg['dates'])}")
        print(f"    Clicks: {last_7_agg['clicks']:,} (sum)")
        print(f"    Impressions: {last_7_agg['impressions']:,} (sum)")
        print(f"    CTR: {last_7_agg['ctr']:.4f} ({last_7_agg['clicks']}/{last_7_agg['impressions']})")
        print(f"    Avg Position: {last_7_agg['avg_position']:.2f}")
        
        print(f"\n  [WINDOW] Previous 7 days ({previous_7_agg['start_date']} → {previous_7_agg['end_date']}):")
        print(f"    Dates: {', '.join(previous_7_agg['dates'])}")
        print(f"    Clicks: {previous_7_agg['clicks']:,} (sum)")
        print(f"    Impressions: {previous_7_agg['impressions']:,} (sum)")
        print(f"    CTR: {previous_7_agg['ctr']:.4f} ({previous_7_agg['clicks']}/{previous_7_agg['impressions']})")
        print(f"    Avg Position: {previous_7_agg['avg_position']:.2f}")
        
        # Compute deltas
        deltas = self.compute_deltas(last_7_agg, previous_7_agg)
        
        # Log deltas
        print(f"\n  [DELTA] Comparison (Last 7 vs Previous 7):")
        print(f"    Clicks: {deltas['clicks']['delta']:+,} ({deltas['clicks']['percentage']:+.1f}%)")
        print(f"    Impressions: {deltas['impressions']['delta']:+,} ({deltas['impressions']['percentage']:+.1f}%)")
        print(f"    CTR: {deltas['ctr']['delta']:+.4f} ({deltas['ctr']['percentage']:+.1f}%)")
        position_status = "improved" if deltas['position']['improved'] else "declined"
        print(f"    Position: {deltas['position']['delta']:+.2f} ({position_status})")
        
        # Calculate last updated
        last_updated_date = rows[0]['date']
        days_ago = (datetime.now().date() - last_updated_date).days
        print(f"\n  Last updated: {days_ago} days ago ({last_updated_date.strftime('%Y-%m-%d')})")
        
        return {
            'property_id': property_id,
            'site_url': site_url,
            'base_domain': base_domain,
            'insufficient_data': False,
            'last_7_days': {
                'start_date': last_7_agg['start_date'],
                'end_date': last_7_agg['end_date'],
                'clicks': last_7_agg['clicks'],
                'impressions': last_7_agg['impressions'],
                'ctr': round(last_7_agg['ctr'], 4),
                'avg_position': round(last_7_agg['avg_position'], 2)
            },
            'previous_7_days': {
                'start_date': previous_7_agg['start_date'],
                'end_date': previous_7_agg['end_date'],
                'clicks': previous_7_agg['clicks'],
                'impressions': previous_7_agg['impressions'],
                'ctr': round(previous_7_agg['ctr'], 4),
                'avg_position': round(previous_7_agg['avg_position'], 2)
            },
            'deltas': {
                'clicks': {
                    'absolute': deltas['clicks']['delta'],
                    'percentage': round(deltas['clicks']['percentage'], 1)
                },
                'impressions': {
                    'absolute': deltas['impressions']['delta'],
                    'percentage': round(deltas['impressions']['percentage'], 1)
                },
                'ctr': {
                    'absolute': round(deltas['ctr']['delta'], 4),
                    'percentage': round(deltas['ctr']['percentage'], 1)
                },
                'position': {
                    'absolute': round(deltas['position']['delta'], 2),
                    'improved': deltas['position']['improved']
                }
            },
            'last_updated': {
                'date': last_updated_date.strftime('%Y-%m-%d'),
                'days_ago': days_ago
            }
        }
    
    def aggregate_all_properties(self, properties: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Compute 7v7 comparisons for all properties
        
        Args:
            properties: List of property dictionaries from database
        
        Returns:
            Dictionary with all comparison results
        """
        print("\n" + "="*80)
        print("PHASE 4: METRICS AGGREGATION & 7v7 COMPARISON")
        print("="*80)
        print(f"Properties to analyze: {len(properties)}")
        print("="*80)
        
        results = []
        properties_with_data = 0
        properties_insufficient = 0
        
        for prop in properties:
            result = self.compute_property_comparison(prop)
            results.append(result)
            
            if result.get('insufficient_data'):
                properties_insufficient += 1
            else:
                properties_with_data += 1
        
        # Print summary
        print("\n" + "="*80)
        print("AGGREGATION SUMMARY")
        print("="*80)
        print(f"✓ Properties analyzed: {len(properties)}")
        print(f"✓ Properties with sufficient data (≥14 days): {properties_with_data}")
        if properties_insufficient > 0:
            print(f"⚠ Properties with insufficient data: {properties_insufficient}")
        print("="*80 + "\n")
        
        # Save to JSON
        output_dir = os.path.join(os.path.dirname(__file__), '..', 'outputs')
        os.makedirs(output_dir, exist_ok=True)
        
        output_file = os.path.join(output_dir, 'property_7v7_comparisons.json')
        
        output_data = {
            'generated_at': datetime.now().isoformat(),
            'total_properties': len(properties),
            'properties_with_data': properties_with_data,
            'properties_insufficient_data': properties_insufficient,
            'comparisons': results
        }
        
        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        print(f"[OUTPUT] JSON saved to: {output_file}\n")
        
        return output_data

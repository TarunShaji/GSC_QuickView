"""
Page Visibility Analyzer V1

Pure structural visibility analysis using impressions only.
NO CTR, NO position, NO health flags - just set logic.

Core Logic:
- P_last = set of pages with impressions in last 7 days
- P_prev = set of pages with impressions in previous 7 days
- New pages: page ∈ P_last AND page ∉ P_prev
- Lost pages: page ∈ P_prev AND page ∉ P_last
- Continuing pages: page ∈ P_prev AND page ∈ P_last
  - Gain: delta_pct >= 40%
  - Drop: delta_pct <= -40%
  - Flat: ignored (not persisted)
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Set, Tuple
from db_persistence import DatabasePersistence
from config.date_windows import ANALYSIS_WINDOW_DAYS, HALF_ANALYSIS_WINDOW


def safe_delta_pct(current: int, previous: int) -> float:
    """
    Compute mathematically safe percentage delta.
    
    Rules:
    - If previous > 0: standard delta calc
    - If previous == 0 and current > 0: +100.0% (growth from zero)
    - If previous == 0 and current == 0: 0.0%
    """
    if previous > 0:
        return round(((current - previous) / previous) * 100, 1)
    elif current > 0:
        return 100.0
    else:
        return 0.0


class PageVisibilityAnalyzer:
    """Analyzes page-level visibility using impressions-only set logic"""
    
    def __init__(self, db: DatabasePersistence):
        self.db = db
    
    def fetch_analysis_metrics(self, account_id: str, property_id: str) -> List[Dict[str, Any]]:
        """
        Fetch page impressions for analysis
        
        Args:
            account_id: UUID of the account
            property_id: UUID of the property
        
        Returns:
            List of dicts with page_url, date, impressions
        """
        return self.db.fetch_page_metrics_for_analysis(account_id, property_id)
    
    def build_page_sets(self, rows: List[Dict[str, Any]]) -> Tuple[Set[str], Set[str]]:
        """
        Build P_last and P_prev sets using date-based filtering
        
        Args:
            rows: All page-date rows for last 14 days
        
        Returns:
            Tuple of (P_last, P_prev) - sets of page URLs
        """
        if not rows:
            return (set(), set())
        
        # Calculate date boundaries
        most_recent_date = max(row['date'] for row in rows)
        
        # Windows: derived from canonical ANALYSIS_WINDOW_DAYS
        window_size = HALF_ANALYSIS_WINDOW
        
        # Last window: most_recent_date - 6 to most_recent_date
        last_7_start = most_recent_date - timedelta(days=window_size - 1)
        
        # Previous window: most_recent_date - 13 to most_recent_date - 7
        prev_7_start = most_recent_date - timedelta(days=(window_size * 2) - 1)
        prev_7_end = most_recent_date - timedelta(days=window_size)
        
        P_last = set()
        P_prev = set()
        
        for row in rows:
            page_url = row['page_url']
            date = row['date']
            
            # Page belongs to P_last if it has impressions in last 7 days
            if last_7_start <= date <= most_recent_date:
                P_last.add(page_url)
            
            # Page belongs to P_prev if it has impressions in previous 7 days
            if prev_7_start <= date <= prev_7_end:
                P_prev.add(page_url)
        
        return (P_last, P_prev)
    
    def classify_pages(self, P_last: Set[str], P_prev: Set[str]) -> Dict[str, Set[str]]:
        """
        Classify pages using set logic
        
        Args:
            P_last: Set of pages with impressions in last 7 days
            P_prev: Set of pages with impressions in previous 7 days
        
        Returns:
            Dict with 'new_pages', 'lost_pages', 'continuing_pages' sets
        """
        return {
            'new_pages': P_last - P_prev,  # In last, not in prev
            'lost_pages': P_prev - P_last,  # In prev, not in last
            'continuing_pages': P_last & P_prev  # In both
        }
    
    def aggregate_page_metrics(self, rows: List[Dict[str, Any]], page_url: str, 
                              start_date: datetime.date, end_date: datetime.date) -> Dict[str, int]:
        """
        Aggregate metrics for a single page over a date range
        
        Args:
            rows: All page-date rows
            page_url: URL to aggregate
            start_date: Start of range (inclusive)
            end_date: End of range (inclusive)
        
        Returns:
            Dict with 'impressions' and 'clicks'
        """
        matching_rows = [
            row for row in rows
            if row['page_url'] == page_url and start_date <= row['date'] <= end_date
        ]
        
        impressions = sum(row.get('impressions', 0) or 0 for row in matching_rows)
        clicks = sum(row.get('clicks', 0) or 0 for row in matching_rows)
        
        return {
            'impressions': impressions,
            'clicks': clicks
        }
    
    def compute_page_deltas(self, rows: List[Dict[str, Any]], continuing_pages: Set[str],
                           most_recent_date: datetime.date) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Compute metric deltas for continuing pages
        Only returns gains (>=40% impressions) and drops (<=-40% impressions)
        
        Args:
            rows: All page-date rows
            continuing_pages: Set of page URLs that appear in both windows
            most_recent_date: Most recent date in dataset
        
        Returns:
            Tuple of (rising, declining) - lists of page dicts
        """
        # Calculate date boundaries using canonical constants
        window_size = HALF_ANALYSIS_WINDOW
        last_7_start = most_recent_date - timedelta(days=window_size - 1)
        prev_7_start = most_recent_date - timedelta(days=ANALYSIS_WINDOW_DAYS - 1)
        prev_7_end = most_recent_date - timedelta(days=window_size)
        
        rising = []
        declining = []
        
        for page_url in continuing_pages:
            # Aggregate metrics for both windows
            last_metrics = self.aggregate_page_metrics(rows, page_url, last_7_start, most_recent_date)
            prev_metrics = self.aggregate_page_metrics(rows, page_url, prev_7_start, prev_7_end)
            
            imps_last = last_metrics['impressions']
            imps_prev = prev_metrics['impressions']
            clicks_last = last_metrics['clicks']
            clicks_prev = prev_metrics['clicks']
            
            # Compute impression delta
            delta = imps_last - imps_prev
            delta_pct = safe_delta_pct(imps_last, imps_prev)
            
            # Compute clicks delta
            clicks_delta = clicks_last - clicks_prev
            clicks_delta_pct = safe_delta_pct(clicks_last, clicks_prev)
            
            # Classify: only persist significant changes
            page_dict = {
                'page_url': page_url,
                'impressions_last_7': imps_last,
                'impressions_prev_7': imps_prev,
                'delta': delta,
                'delta_pct': round(delta_pct, 1),
                'clicks_last_7': clicks_last,
                'clicks_prev_7': clicks_prev,
                'clicks_delta': clicks_delta,
                'clicks_delta_pct': round(clicks_delta_pct, 1)
            }
            
            if delta_pct >= 40:
                rising.append(page_dict)
            elif delta_pct <= -40:
                declining.append(page_dict)
            # else: flat page, ignore (do not persist)
        
        return (rising, declining)
    
    def analyze_property(self, account_id: str, property_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Full visibility analysis for one property
        
        Args:
            account_id: UUID of the account
            property_data: Dict with 'id', 'site_url', 'base_domain'
        
        Returns:
            Dict with new_pages, lost_pages, gains, drops
        """
        property_id = property_data['id']
        site_url = property_data['site_url']
        base_domain = property_data['base_domain']
        
        print(f"\n[PROPERTY] {base_domain}")
        print(f"  Site URL: {site_url}")
        
        # Fetch page metrics for analysis (impressions only)
        rows = self.fetch_analysis_metrics(account_id, property_id)
        
        # Safety validation
        if not rows or len(set(row['date'] for row in rows)) < ANALYSIS_WINDOW_DAYS:
            print(f"  [WARNING] Insufficient data: only {len(set(row['date'] for row in rows))} days available (need {ANALYSIS_WINDOW_DAYS})")
            return {
                'property_id': property_id,
                'new_pages': [],
                'lost_pages': [],
                'gains': [],
                'drops': [],
                'insufficient_data': True
            }
        
        print(f"  [DATA] Retrieved {len(rows):,} page-date rows for last 14 days")
        
        # Build sets
        P_last, P_prev = self.build_page_sets(rows)
        print(f"  [SETS] P_last: {len(P_last)} unique pages, P_prev: {len(P_prev)} unique pages")
        
        # Classify pages
        classification = self.classify_pages(P_last, P_prev)
        new_pages_set = classification['new_pages']
        lost_pages_set = classification['lost_pages']
        continuing_pages = classification['continuing_pages']
        
        print(f"  [CLASSIFICATION]")
        print(f"    New pages: {len(new_pages_set)}")
        print(f"    Lost pages: {len(lost_pages_set)}")
        print(f"    Continuing pages: {len(continuing_pages)}")
        
        # Get most recent date for delta computation
        most_recent_date = max(row['date'] for row in rows)
        
        # Compute deltas for continuing pages (only gains and drops)
        gains, drops = self.compute_page_deltas(rows, continuing_pages, most_recent_date)
        
        print(f"    Gains (>=40%): {len(gains)}")
        print(f"    Drops (<=-40%): {len(drops)}")
        
        # Build detailed lists for new and lost pages
        last_7_start = most_recent_date - timedelta(days=6)
        prev_7_start = most_recent_date - timedelta(days=13)
        prev_7_end = most_recent_date - timedelta(days=7)
        
        new_pages = []
        for page_url in new_pages_set:
            metrics = self.aggregate_page_metrics(rows, page_url, last_7_start, most_recent_date)
            new_pages.append({
                'page_url': page_url,
                'impressions_last_7': metrics['impressions'],
                'impressions_prev_7': 0,
                'delta': metrics['impressions'],
                'delta_pct': safe_delta_pct(metrics['impressions'], 0),
                'clicks_last_7': metrics['clicks'],
                'clicks_prev_7': 0,
                'clicks_delta': metrics['clicks'],
                'clicks_delta_pct': safe_delta_pct(metrics['clicks'], 0)
            })
        
        lost_pages = []
        for page_url in lost_pages_set:
            metrics = self.aggregate_page_metrics(rows, page_url, prev_7_start, prev_7_end)
            lost_pages.append({
                'page_url': page_url,
                'impressions_last_7': 0,
                'impressions_prev_7': metrics['impressions'],
                'delta': -metrics['impressions'],
                'delta_pct': safe_delta_pct(0, metrics['impressions']),
                'clicks_last_7': 0,
                'clicks_prev_7': metrics['clicks'],
                'clicks_delta': -metrics['clicks'],
                'clicks_delta_pct': safe_delta_pct(0, metrics['clicks'])
            })
        
        # Sort by impressions (descending)
        new_pages.sort(key=lambda x: x['impressions_last_7'], reverse=True)
        lost_pages.sort(key=lambda x: x['impressions_prev_7'], reverse=True)
        gains.sort(key=lambda x: x['delta'], reverse=True)
        drops.sort(key=lambda x: abs(x['delta']), reverse=True)
        
        # Log top anomalies
        if lost_pages:
            print(f"\n  [LOST PAGES] Top 3:")
            for page in lost_pages[:3]:
                print(f"    {page['page_url']} (was {page['impressions_prev_7']} impressions)")
        
        if drops:
            print(f"\n  [DROPS] Top 3:")
            for page in drops[:3]:
                print(f"    {page['page_url']}: {page['impressions_prev_7']} → {page['impressions_last_7']} ({page['delta_pct']}%)")
        
        return {
            'property_id': property_id,
            'site_url': site_url,
            'base_domain': base_domain,
            'insufficient_data': False,
            'new_pages': new_pages,
            'lost_pages': lost_pages,
            'gains': gains,
            'drops': drops
        }
    
    def analyze_all_properties(self, properties: List[Dict[str, Any]], account_id: str) -> Dict[str, Any]:
        """
        Analyze all properties and persist results to database.
        
        Args:
            properties: List of property dicts from database
            account_id: UUID of the account
        
        Returns:
            Summary dict with aggregated results
        """
        print("\n" + "="*80)
        print("PAGE VISIBILITY ANALYSIS V1")
        print("="*80)
        print(f"Properties to analyze: {len(properties)}")
        print("="*80)
        
        results = []
        total_new = 0
        total_lost = 0
        total_gains = 0
        total_drops = 0
        
        for prop in properties:
            result = self.analyze_property(account_id, prop)
            results.append(result)
            
            # Persist to database
            if not result['insufficient_data']:
                self.db.persist_page_visibility_analysis(
                    property_id=prop['id'],
                    analysis_results={
                        'new_pages': result['new_pages'],
                        'lost_pages': result['lost_pages'],
                        'gains': result['gains'],
                        'drops': result['drops']
                    }
                )
                
                total_new += len(result['new_pages'])
                total_lost += len(result['lost_pages'])
                total_gains += len(result['gains'])
                total_drops += len(result['drops'])
        
        # Print summary
        print("\n" + "="*80)
        print("VISIBILITY SUMMARY")
        print("="*80)
        print(f"✓ Properties analyzed: {len(properties)}")
        print(f"✓ Total new pages: {total_new}")
        print(f"✓ Total lost pages: {total_lost}")
        print(f"✓ Total gains: {total_gains}")
        print(f"✓ Total drops: {total_drops}")
        print("="*80 + "\n")
        
        # Optional: Save JSON output for CLI/debugging
        output_dir = os.path.join(os.path.dirname(__file__), '..', 'outputs')
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, 'page_visibility_analysis.json')
        
        output_data = {
            'generated_at': datetime.now().isoformat(),
            'total_properties': len(properties),
            'total_new_pages': total_new,
            'total_lost_pages': total_lost,
            'total_gains': total_gains,
            'total_drops': total_drops,
            'comparisons': results
        }
        
        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2, default=str)
        
        print(f"[DEBUG] JSON saved to: {output_file}\n")
        
        return output_data

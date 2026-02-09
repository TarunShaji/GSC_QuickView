"""
Page Visibility Analyzer

Pure SQL-based visibility analysis using set logic.
NO API calls - operates entirely on stored page_daily_metrics data.

Core Logic:
- P_last = set of pages with impressions in last 7 days
- P_prev = set of pages with impressions in previous 7 days
- New pages: page ∈ P_last AND page ∉ P_prev
- Lost pages: page ∈ P_prev AND page ∉ P_last (HIGH SEVERITY)
- Continuing pages: page ∈ P_prev AND page ∈ P_last (only these get deltas)
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Set, Tuple
from decimal import Decimal
from db_persistence import DatabasePersistence


class PageVisibilityAnalyzer:
    """Analyzes page-level visibility using set-based logic"""
    
    def __init__(self, db: DatabasePersistence):
        self.db = db
        self.low_volume_threshold = 10  # Ignore pages with <10 total impressions for drop/gain classification
    
    def fetch_last_14_days_pages(self, property_id: str) -> List[Dict[str, Any]]:
        """
        Fetch all page metrics for last 14 days
        
        Args:
            property_id: UUID of the property
        
        Returns:
            List of dicts with page_url, date, clicks, impressions, ctr, position
        """
        return self.db.fetch_page_metrics_last_14_days(property_id)
    
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
        # Assuming rows are ordered DESC, first row is most recent
        most_recent_date = max(row['date'] for row in rows)
        
        # Last 7 days: most_recent_date - 6 to most_recent_date (inclusive)
        last_7_start = most_recent_date - timedelta(days=6)
        
        # Previous 7 days: most_recent_date - 13 to most_recent_date - 7 (inclusive)
        prev_7_start = most_recent_date - timedelta(days=13)
        prev_7_end = most_recent_date - timedelta(days=7)
        
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
                               start_date: datetime.date, end_date: datetime.date) -> Dict[str, Any]:
        """
        Aggregate metrics for a single page over a date range
        
        Args:
            rows: All page-date rows
            page_url: URL to aggregate
            start_date: Start of range (inclusive)
            end_date: End of range (inclusive)
        
        Returns:
            Dict with aggregated clicks, impressions, ctr, position
        """
        matching_rows = [
            row for row in rows
            if row['page_url'] == page_url and start_date <= row['date'] <= end_date
        ]
        
        if not matching_rows:
            return {
                'clicks': 0,
                'impressions': 0,
                'ctr': 0.0,
                'avg_position': 0.0
            }
        
        total_clicks = sum(float(row['clicks']) for row in matching_rows)
        total_impressions = sum(float(row['impressions']) for row in matching_rows)
        
        # Computed CTR (NOT average of CTRs)
        computed_ctr = total_clicks / total_impressions if total_impressions > 0 else 0.0
        
        # Average position
        avg_position = sum(float(row['position']) for row in matching_rows) / len(matching_rows)
        
        return {
            'clicks': int(total_clicks),
            'impressions': int(total_impressions),
            'ctr': computed_ctr,
            'avg_position': avg_position
        }
    
    def compute_page_deltas(self, rows: List[Dict[str, Any]], continuing_pages: Set[str],
                           most_recent_date: datetime.date) -> List[Dict[str, Any]]:
        """
        Compute impression deltas ONLY for continuing pages
        
        Args:
            rows: All page-date rows
            continuing_pages: Set of page URLs that appear in both windows
            most_recent_date: Most recent date in dataset
        
        Returns:
            List of page delta dicts with classification
        """
        # Calculate date boundaries
        last_7_start = most_recent_date - timedelta(days=6)
        prev_7_start = most_recent_date - timedelta(days=13)
        prev_7_end = most_recent_date - timedelta(days=7)
        
        page_deltas = []
        
        for page_url in continuing_pages:
            # Aggregate last 7 days
            last_7 = self.aggregate_page_metrics(rows, page_url, last_7_start, most_recent_date)
            
            # Aggregate previous 7 days
            prev_7 = self.aggregate_page_metrics(rows, page_url, prev_7_start, prev_7_end)
            
            # Compute deltas
            impressions_delta = last_7['impressions'] - prev_7['impressions']
            impressions_pct = (impressions_delta / prev_7['impressions'] * 100) if prev_7['impressions'] > 0 else 0.0
            
            # Apply low-volume threshold for classification
            total_impressions = last_7['impressions'] + prev_7['impressions']
            
            # Classify (only if above threshold)
            classification = 'flat'
            if total_impressions >= self.low_volume_threshold:
                if impressions_pct >= 50:
                    classification = 'significant_gain'
                elif impressions_pct <= -50:
                    classification = 'significant_drop'
            
            page_deltas.append({
                'page_url': page_url,
                'impressions_last_7': last_7['impressions'],
                'impressions_prev_7': prev_7['impressions'],
                'delta': impressions_delta,
                'delta_pct': round(impressions_pct, 1),
                'classification': classification,
                'clicks_last_7': last_7['clicks'],
                'clicks_prev_7': prev_7['clicks'],
                'ctr_last_7': last_7['ctr'],
                'ctr_prev_7': prev_7['ctr'],
                'position_last_7': last_7['avg_position'],
                'position_prev_7': prev_7['avg_position']
            })
        
        return page_deltas
    
    def analyze_property(self, property_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Full visibility analysis for one property
        
        Args:
            property_data: Dict with 'id', 'site_url', 'base_domain'
        
        Returns:
            Dict with summary and detailed page lists
        """
        property_id = property_data['id']
        site_url = property_data['site_url']
        base_domain = property_data['base_domain']
        
        print(f"\n[PROPERTY] {base_domain}")
        print(f"  Site URL: {site_url}")
        
        # Fetch last 14 days of page metrics
        rows = self.fetch_last_14_days_pages(property_id)
        
        if not rows:
            print(f"  [WARNING] No page metrics data available")
            return {
                'property_id': property_id,
                'site_url': site_url,
                'base_domain': base_domain,
                'insufficient_data': True,
                'summary': {
                    'new_pages': 0,
                    'lost_pages': 0,
                    'continuing_pages': 0,
                    'significant_drops': 0,
                    'significant_gains': 0
                },
                'details': {
                    'new_pages': [],
                    'lost_pages': [],
                    'continuing_with_deltas': []
                }
            }
        
        print(f"  [DATA] Retrieved {len(rows):,} page-date rows for last 14 days")
        
        # Build sets
        P_last, P_prev = self.build_page_sets(rows)
        print(f"  [SETS] P_last: {len(P_last)} unique pages, P_prev: {len(P_prev)} unique pages")
        
        # Classify pages
        classification = self.classify_pages(P_last, P_prev)
        new_pages = classification['new_pages']
        lost_pages = classification['lost_pages']
        continuing_pages = classification['continuing_pages']
        
        print(f"  [CLASSIFICATION]")
        print(f"    New pages: {len(new_pages)}")
        print(f"    Lost pages: {len(lost_pages)}")
        print(f"    Continuing pages: {len(continuing_pages)}")
        
        # Get most recent date for delta computation
        most_recent_date = max(row['date'] for row in rows)
        
        # Compute deltas for continuing pages
        page_deltas = self.compute_page_deltas(rows, continuing_pages, most_recent_date)
        
        # Count significant changes
        significant_drops = sum(1 for p in page_deltas if p['classification'] == 'significant_drop')
        significant_gains = sum(1 for p in page_deltas if p['classification'] == 'significant_gain')
        
        print(f"    Significant drops (>50%): {significant_drops}")
        print(f"    Significant gains (>50%): {significant_gains}")
        
        # Build detailed lists
        last_7_start = most_recent_date - timedelta(days=6)
        prev_7_start = most_recent_date - timedelta(days=13)
        prev_7_end = most_recent_date - timedelta(days=7)
        
        new_pages_details = []
        for page_url in new_pages:
            metrics = self.aggregate_page_metrics(rows, page_url, last_7_start, most_recent_date)
            new_pages_details.append({
                'page_url': page_url,
                'impressions_last_7': metrics['impressions']
            })
        
        lost_pages_details = []
        for page_url in lost_pages:
            metrics = self.aggregate_page_metrics(rows, page_url, prev_7_start, prev_7_end)
            lost_pages_details.append({
                'page_url': page_url,
                'impressions_prev_7': metrics['impressions']
            })
        
        # Sort by impressions (descending)
        new_pages_details.sort(key=lambda x: x['impressions_last_7'], reverse=True)
        lost_pages_details.sort(key=lambda x: x['impressions_prev_7'], reverse=True)
        page_deltas.sort(key=lambda x: abs(x['delta']), reverse=True)
        
        # Log top anomalies
        if lost_pages_details:
            print(f"\n  [LOST PAGES] Top 3:")
            for page in lost_pages_details[:3]:
                print(f"    {page['page_url']} (was {page['impressions_prev_7']} impressions)")
        
        if significant_drops > 0:
            print(f"\n  [SIGNIFICANT DROPS] Top 3:")
            drops = [p for p in page_deltas if p['classification'] == 'significant_drop']
            for page in drops[:3]:
                print(f"    {page['page_url']}: {page['impressions_prev_7']} → {page['impressions_last_7']} ({page['delta_pct']}%)")
        
        return {
            'property_id': property_id,
            'site_url': site_url,
            'base_domain': base_domain,
            'insufficient_data': False,
            'summary': {
                'new_pages': len(new_pages),
                'lost_pages': len(lost_pages),
                'continuing_pages': len(continuing_pages),
                'significant_drops': significant_drops,
                'significant_gains': significant_gains
            },
            'details': {
                'new_pages': new_pages_details,
                'lost_pages': lost_pages_details,
                'continuing_with_deltas': page_deltas
            }
        }
    
    def analyze_all_properties(self, properties: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze all properties and persist results to database.
        
        Args:
            properties: List of property dicts from database
        
        Returns:
            Summary dict with aggregated results
        """
        print("\n" + "="*80)
        print("PAGE VISIBILITY ANALYSIS")
        print("="*80)
        print(f"Properties to analyze: {len(properties)}")
        print("="*80)
        
        results = []
        total_new = 0
        total_lost = 0
        total_drops = 0
        total_gains = 0
        
        for prop in properties:
            result = self.analyze_property(prop)
            results.append(result)
            
            # Persist to database (primary output)
            if not result['insufficient_data']:
                self.db.persist_page_visibility_analysis(
    property_id=prop['id'],
    analysis_results={
        'new_pages': result['details']['new_pages'],
        'lost_pages': result['details']['lost_pages'],
        'significant_drops': [
            p for p in result['details']['continuing_with_deltas']
            if p['classification'] == 'significant_drop'
        ],
        'significant_gains': [
            p for p in result['details']['continuing_with_deltas']
            if p['classification'] == 'significant_gain'
        ]
    }
)
                
                total_new += result['summary']['new_pages']
                total_lost += result['summary']['lost_pages']
                total_drops += result['summary']['significant_drops']
                total_gains += result['summary']['significant_gains']
        
        # Print summary
        print("\n" + "="*80)
        print("VISIBILITY SUMMARY")
        print("="*80)
        print(f"✓ Properties analyzed: {len(properties)}")
        print(f"✓ Total new pages: {total_new}")
        print(f"✓ Total lost pages: {total_lost}")
        print(f"✓ Total significant drops: {total_drops}")
        print(f"✓ Total significant gains: {total_gains}")
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
            'total_significant_drops': total_drops,
            'total_significant_gains': total_gains,
            'comparisons': results
        }
        
        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2, default=str)
        
        print(f"[DEBUG] JSON saved to: {output_file}\n")
        
        return output_data

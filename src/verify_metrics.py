"""
Quick verification script to check database metrics count
"""

from db_persistence import DatabasePersistence

def main():
    db = DatabasePersistence()
    db.connect()
    
    try:
        # Count total metric rows
        db.cursor.execute("SELECT COUNT(*) as c FROM property_daily_metrics")
        total_metrics = db.cursor.fetchone()["c"]
        print(f"[DEBUG] Total metric rows in database: {total_metrics}")
        
        # Count metrics per property
        db.cursor.execute("""
            SELECT 
                w.base_domain,
                p.site_url,
                COUNT(m.id) as metric_count
            FROM properties p
            JOIN websites w ON p.website_id = w.id
            LEFT JOIN property_daily_metrics m ON p.id = m.property_id
            GROUP BY w.base_domain, p.site_url
            ORDER BY w.base_domain, p.site_url
        """)
        
        results = db.cursor.fetchall()
        
        print("\nMetrics per property:")
        print("="*80)
        for row in results:
            print(f"{row['base_domain']:30} | {row['site_url']:50} | {row['metric_count']:3} rows")
        
        print("="*80)
        print(f"Total properties: {len(results)}")
        print(f"Total metric rows: {total_metrics}")
        
    finally:
        db.disconnect()

if __name__ == '__main__':
    main()

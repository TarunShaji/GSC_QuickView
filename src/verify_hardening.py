import time
from db_persistence import DatabasePersistence, init_db_pool, close_db_pool
from main import run_pipeline
from settings import settings
import uuid
from datetime import datetime, timedelta

def test_atomic_guards(account_id):
    print("\n--- Testing Atomic Guards ---")
    db = DatabasePersistence()
    db.connect()
    
    # Create a dummy run
    run_id = db.start_pipeline_run(account_id)
    print(f"Started run {run_id} for account {account_id}")
    
    # Update state - should succeed
    db.update_pipeline_state(account_id, run_id, current_step="Step 1")
    print("Update 1 (Active) - Checked")
    
    # Manually mark as finished
    db.update_pipeline_state(account_id, run_id, is_running=False)
    print("Marked as finished - Checked")
    
    # Try to update again - should log warning and not change data (but updated_at might change? No, WHERE clause prevents match)
    db.update_pipeline_state(account_id, run_id, current_step="Zombie Step")
    
    # Verify it's NOT Step 2
    db.cursor.execute("SELECT current_step FROM pipeline_runs WHERE id = %s", (run_id,))
    step = db.cursor.fetchone()['current_step']
    if step == "Step 1":
        print("✅ Atomic Guard successfully prevented zombie update.")
    else:
        print(f"❌ Atomic Guard FAILED. Current step is: {step}")
    
    db.disconnect()

def test_timeouts(account_id):
    print("\n--- Testing Heartbeat Timeouts ---")
    db = DatabasePersistence()
    db.connect()
    
    run_id = db.start_pipeline_run(account_id)
    
    # 1. Test heartbeat timeout (20m)
    # Manually set updated_at back
    db.cursor.execute("""
        UPDATE pipeline_runs 
        SET updated_at = NOW() - INTERVAL '21 minutes',
            started_at = NOW() - INTERVAL '30 minutes'
        WHERE id = %s
    """, (run_id,))
    db.connection.commit()
    
    print("Simulated 21m stale heartbeat. Cleaning up...")
    db.cleanup_stale_runs(account_id)
    
    state = db.fetch_pipeline_state(account_id)
    if not state['is_running'] and "no heartbeat" in state['error'].lower():
        print("✅ Heartbeat timeout successfully terminated run.")
    else:
        print(f"❌ Heartbeat timeout FAILED. State: {state}")

    # 2. Test hard timeout (2h)
    print("Preparing 2h hard timeout test...")
    run_id_2 = db.start_pipeline_run(account_id)
    db.cursor.execute("""
        UPDATE pipeline_runs 
        SET started_at = NOW() - INTERVAL '121 minutes',
            updated_at = NOW() - INTERVAL '5 minutes'
        WHERE id = %s
    """, (run_id_2,))
    db.connection.commit()
    
    print("Simulated >2h hard runtime. Cleaning up...")
    db.cleanup_stale_runs(account_id)
    
    state_2 = db.fetch_pipeline_state(account_id)
    if state_2 and not state_2['is_running'] and "hard timeout" in state_2['error'].lower():
        print("✅ Hard timeout successfully terminated run.")
    else:
        print(f"❌ Hard timeout FAILED. State: {state_2}")
        
    db.disconnect()

if __name__ == "__main__":
    init_db_pool(settings.DATABASE_URL)
    try:
        db = DatabasePersistence()
        db.connect()
        accounts = db.fetch_all_accounts()
        db.disconnect()
        
        if not accounts:
            print("❌ No accounts found in DB. Please login first.")
        else:
            account_id = accounts[0]['id']
            print(f"Using account: {accounts[0]['google_email']} ({account_id})")
            
            # Use real account ID but unique run IDs
            test_atomic_guards(account_id)
            test_timeouts(account_id)
    finally:
        close_db_pool()

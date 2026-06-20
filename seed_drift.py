import sys
import os
from datetime import datetime, timedelta

sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))
from db import add_spend_history

def seed_data():
    account = "default_account"
    # Seed 14 days of data showing drift closing
    today = datetime.now()
    
    # 14 days ago, high actual, high predicted
    for i in range(14, -1, -1):
        d = today - timedelta(days=i)
        date_str = d.strftime('%Y-%m-%d')
        
        # Start at $500 actual, $300 predicted
        # Over time, actual drops as optimizations are applied
        if i > 10:
            actual = 500.0 + (i * 2)
            predicted = 300.0
        elif i > 5:
            actual = 400.0 + (i * 1.5)
            predicted = 280.0
        else:
            actual = 320.0 + (i * 1.2)
            predicted = 300.0
            
        print(f"Adding {date_str}: Actual={actual}, Predicted={predicted}")
        add_spend_history(account, date_str, actual, predicted)
        
    print("Dummy drift data seeded successfully!")

if __name__ == "__main__":
    seed_data()

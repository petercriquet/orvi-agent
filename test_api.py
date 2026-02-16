import requests
import json
import time

def test_api():
    url = "http://localhost:8000/execute"
    
    # Load data from local files to construct payload
    try:
        with open("sequences.json", "r", encoding="utf-8") as f:
            sequences = json.load(f)
        with open("coordinates.json", "r", encoding="utf-8") as f:
            coordinates = json.load(f)
    except FileNotFoundError:
        print("Error: sequences.json or coordinates.json not found.")
        return

    payload = {
        "sequences": sequences,
        "coordinates": coordinates
    }

    print(f"Sending request to {url}...")
    try:
        start_time = time.time()
        response = requests.post(url, json=payload, timeout=300) # Long timeout for browser automation
        end_time = time.time()
        
        print(f"Response Status: {response.status_code}")
        print(f"Time Taken: {end_time - start_time:.2f}s")
        
        if response.status_code == 200:
            data = response.json()
            print("Success:", data.get("success"))
            print("Screenshot:", data.get("screenshot"))
            print("Logs count:", len(data.get("logs")))
            if not data.get("success"):
                print("Logs:", json.dumps(data.get("logs"), indent=2))
        else:
            print("Error Response:", response.text)
            
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    # Wait for server to start if running immediately after
    time.sleep(2) 
    test_api()

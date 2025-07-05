import os
import requests
import json

CHEMSPIDER_API_KEY = "xduPDRiOrYasBMYJbmIEf4d9i90J2B3G2585r1tk"
print(f"Using ChemSpider API key: {CHEMSPIDER_API_KEY}")

def get_chemspider_csid_from_cas(cas_number):
    url = "https://api.rsc.org/compounds/v1/filter/name"
    headers = {
        'apikey': CHEMSPIDER_API_KEY,
        'Content-Type': 'application/json'
    }
    try:
        payload = {"name": cas_number}
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        filter_id = data.get("queryId")
        if not filter_id:
            print(f"No filterId returned for CAS {cas_number}")
            return None

        results_url = f"https://api.rsc.org/compounds/v1/filter/{filter_id}/results"
        results = requests.get(results_url, headers=headers)
        results.raise_for_status()
        csids = results.json().get("results", [])

        if csids:
            csid = csids[0]
            url_details = f"https://api.rsc.org/compounds/v1/records/{csid}/details"
            res2 = requests.get(url_details, headers=headers, timeout=10)
            res2.raise_for_status()
            details = res2.json()

            print(json.dumps(details, indent=2))  # Debug print entire response

            # Example: extract hazard info from details['properties']
            properties = details.get('properties', [])
            hazards = []
            for prop in properties:
                if 'hazard' in prop.get('name', '').lower():
                    val = prop.get('value')
                    if val:
                        hazards.append(val)

            hazard_info = "\n".join(hazards) if hazards else "No hazard info found"
            print("Hazard info:\n", hazard_info)

            # Return both CSID and hazard info or just hazard info
            return csid, hazard_info
        else:
            print(f"No CSIDs returned for CAS {cas_number}")
            return None

    except requests.exceptions.HTTPError as e:
        print(f"HTTP error: {e}")
        print(response.text)
        return None
    except Exception as e:
        print(f"Error retrieving CSID from ChemSpider: {e}")
        return None


result = get_chemspider_csid_from_cas("109-99-9")
print("Result:", result)
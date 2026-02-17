import asyncio
import sys
import json
import logging
import os
# Import the SequenceExecutor class from the existing module
from sequence_executor import SequenceExecutor

# Setup basic logging to console
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- HARDCODED DATA FOR DEMO ---

COORDINATES = {
    "1": "7364",
    "2": "3001",
    "3": "5198",
    "4": "3520",
    "5": "7997",
    "6": "5871",
    "7": "1486",
    "8": "0501",
    "9": "8664",
    "10": "7625",
    "11": "6825",
    "12": "5461",
    "13": "5960",
    "14": "0239",
    "15": "7533",
    "16": "7955",
    "17": "2508",
    "18": "0853",
    "19": "5038",
    "20": "3885",
    "21": "7308",
    "22": "8822",
    "23": "2461",
    "24": "5216",
    "25": "7545",
    "26": "4748",
    "27": "9773",
    "28": "7605",
    "29": "1762",
    "30": "2077",
    "31": "0265",
    "32": "4013",
    "33": "8380",
    "34": "4454",
    "35": "8225",
    "36": "8344",
    "37": "6015",
    "38": "9082",
    "39": "4151",
    "40": "6573"
}

SEQUENCES = [
    {
        "title": "Iniciar sesión",
        "intents_number": 3,
        "target_element": "ibp-quick-access",
        "target_element_wait": 5,
        "steps": [
            {
                "action": "navigate",
                "data": "https://ibp.bhd.com.do/#/login",
                "wait_after": 2
            },
            {
                "action": "input",
                "element": "#userName",
                "data": "env:BHD_USER",
                "wait_after": 1
            },
            {
                "action": "input",
                "element": "#password",
                "data": "env:BHD_PASS",
                "wait_after": 1
            },
            {
                "action": "click",
                "element": "button:has-text('Entrar')",
                "wait_after": 3
            }
        ]
    },
    {
        "title": "Navegar a area de pagos",
        "intents_number": 3,
        "target_element": "p-select[inputid='beneficiary']",
        "target_element_wait": 5,
        "steps": [
            {
                "action": "navigate",
                "data": "https://ibp.bhd.com.do/#/bhd/payments-transfers/OB",
                "wait_after": 5
            },
            {
                "action": "click",
                "element": "button:has-text('Entendido')",
                "optional": True,
                "wait_after": 2
            },
            {
                "action": "click",
                "element": "p-select[inputid='channel']",
                "wait_after": 2
            },
            {
                "action": "click",
                "element": "li:has-text('A tercero en BHD')",
                "wait_after": 2
            },
            {
                "action": "click",
                "element": "p-select[inputid='debitProduct']",
                "wait_after": 2
            },
            {
                "action": "click",
                "element": "li:has-text('17155440010')",
                "wait_after": 2
            }
        ]
    },
    {
        "title": "Seleccionar Beneficiario y Monto",
        "intents_number": 3,
        "target_element": "input[name='positionKey']",
        "target_element_wait": 5,
        "steps": [
            {
                "action": "click",
                "element": "p-select[inputid='beneficiary']",
                "wait_after": 2
            },
            {
                "action": "click",
                "element": "li:has-text('CRIQUET, PETER ALEXANDER')",
                "wait_after": 2
            },
            {
                "action": "input",
                "element": "input[name='amount']",
                "data": "10",
                "wait_after": 2
            },
            {
                "action": "click",
                "element": "button:has-text('Continuar')",
                "wait_after": 5
            }
        ]
    },
    {
        "title": "Ingresar Token de Coordenadas",
        "intents_number": 3,
        "target_element": "button:has-text('Realizar otra transacción')",
        "target_element_wait": 30,
        "steps": [
            {
                "action": "wait",
                "wait_after": 5
            },
            {
                "action": "dynamic_input",
                "element": "input[name='positionKey']",
                "data": "p-inputgroup-addon",
                "lookup_source": "coordinates.json",
                "wait_after": 1
            },
            {
                "action": "click",
                "element": "button:has-text('Realizar transacción')",
                "wait_after": 2
            }
        ]
    }
]

# --- MAIN EXECUTION ---

async def main():
    print("🚀 Starting Orvi-Agent DEMO Sequence...")
    print("----------------------------------------")
    
    executor = SequenceExecutor()
    
    try:
        # Pass the hardcoded dictionary instead of using external files
        result = await executor.execute(SEQUENCES, COORDINATES)
        
        print("\n----------------------------------------")
        if result["success"]:
            print("✅ DEMO COMPLETED SUCCESSFULLY!")
            print(f"📸 Screenshot saved: {result.get('screenshot')}")
        else:
            print("❌ DEMO FAILED.")
            if result.get("logs"):
                print("Last logs:")
                for log in result["logs"][-5:]:
                    print(log)
                    
    except Exception as e:
        print(f"🔥 CRITICAL ERROR: {e}")
    
    print("\n----------------------------------------")
    input("Press Enter to exit...")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())

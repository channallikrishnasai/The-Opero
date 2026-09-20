# actions/background_monitor.py
"""
Background Monitor Action for Brahma AI.

Allows the AI to schedule background polling for system health, crypto prices, or website uptime.
"""

import threading
import time
import requests
import json
from datetime import datetime
from actions.system_manager import get_system_health

_monitors = {}
_monitor_lock = threading.Lock()
_speech_sink = None

# The daemon below runs on its own thread, so a triggered alert is parked here
# until the assistant loop drains it with check_all() and speaks it in its own
# voice.  (Before, the alert was handed to an unset sink and dropped, while
# check_all() returned None — which the caller iterated, logging
# "'NoneType' object is not iterable" every cycle.)
_pending_alerts: list[str] = []
_alert_lock = threading.Lock()

def set_monitor_speech_sink(sink_fn):
    global _speech_sink
    _speech_sink = sink_fn

def _monitor_loop():
    while True:
        time.sleep(10)
        with _monitor_lock:
            current_time = time.time()
            for m_id, m in list(_monitors.items()):
                if current_time - m['last_check'] >= m['interval']:
                    m['last_check'] = current_time
                    _run_check(m_id, m)

def _run_check(m_id, m):
    try:
        alert_msg = None
        
        if m['type'] == 'system':
            health = get_system_health()
            if m['target'] == 'ram' and health['ram_usage_percent'] > m['threshold']:
                alert_msg = f"Alert: RAM usage has exceeded {m['threshold']}%. Currently at {health['ram_usage_percent']}%."
            elif m['target'] == 'cpu' and health['cpu_usage_percent'] > m['threshold']:
                alert_msg = f"Alert: CPU usage has exceeded {m['threshold']}%. Currently at {health['cpu_usage_percent']}%."
                
        elif m['type'] == 'crypto':
            # Target should be a coin id like 'bitcoin'
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={m['target']}&vs_currencies=usd"
            resp = requests.get(url, timeout=5).json()
            if m['target'] in resp:
                price = resp[m['target']]['usd']
                # Condition: "above" or "below"
                if m['condition'] == 'above' and price > m['threshold']:
                    alert_msg = f"Alert: {m['target'].capitalize()} has gone above ${m['threshold']}. Current price is ${price}."
                elif m['condition'] == 'below' and price < m['threshold']:
                    alert_msg = f"Alert: {m['target'].capitalize()} has dropped below ${m['threshold']}. Current price is ${price}."
                    
        elif m['type'] == 'website':
            try:
                resp = requests.get(m['target'], timeout=5)
                if resp.status_code >= 400:
                    alert_msg = f"Alert: Website {m['target']} is returning status code {resp.status_code}."
            except Exception:
                alert_msg = f"Alert: Website {m['target']} appears to be down or unreachable."

        if alert_msg:
            # Alert triggered! Queue it, then drop the monitor so a threshold
            # that stays tripped cannot re-alert on every single cycle.
            with _alert_lock:
                _pending_alerts.append(alert_msg)
            if _speech_sink:
                _speech_sink(alert_msg)
            del _monitors[m_id]
            
    except Exception as e:
        print(f"[Monitor] Error checking {m_id}: {e}")

# Start the daemon loop
threading.Thread(target=_monitor_loop, daemon=True).start()

def add_monitor(monitor_type: str, target: str, threshold: float, condition: str = "above", interval_sec: int = 60) -> str:
    m_id = f"{monitor_type}_{target}_{int(time.time())}"
    with _monitor_lock:
        _monitors[m_id] = {
            "type": monitor_type,
            "target": target.lower(),
            "threshold": threshold,
            "condition": condition,
            "interval": interval_sec,
            "last_check": time.time()
        }
    return f"Started monitoring {monitor_type} ({target}) every {interval_sec} seconds."

def get_monitors() -> str:
    with _monitor_lock:
        if not _monitors:
            return "No active background monitors."
        return json.dumps(_monitors, indent=2)

def run(parameters: dict, player=None, session_memory=None) -> str:
    action = parameters.get("action", "add")
    if action == "list":
        return get_monitors()
    
    m_type = parameters.get("type")
    target = parameters.get("target")
    threshold = parameters.get("threshold", 0.0)
    condition = parameters.get("condition", "above")
    interval = parameters.get("interval", 60)
    
    if not m_type or not target:
        return "You must provide a 'type' (system/crypto/website) and a 'target' (ram/cpu/bitcoin/url)."
        
    res = add_monitor(m_type, target, float(threshold), condition, int(interval))
    if player:
        player.write_log(f"SYS: {res}")
    return res
def remove_monitor(target: str) -> str:
    with _monitor_lock:
        keys_to_remove = [k for k, v in _monitors.items() if v['target'] == target.lower()]
        for k in keys_to_remove:
            del _monitors[k]
        if keys_to_remove:
            return f"Removed monitor for {target}."
        return f"No monitor found for {target}."

def list_monitors() -> list[str]:
    with _monitor_lock:
        return [f"{v['type']} - {v['target']}" for v in _monitors.values()]

def check_all() -> list[str]:
    """Return every alert raised since the last call, and clear the queue."""
    with _alert_lock:
        alerts = list(_pending_alerts)
        _pending_alerts.clear()
    return alerts
